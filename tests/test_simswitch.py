"""The simswitch adapter and AT transport, driven against a fake modem and a
fake uci. Covers the reading, a switch, an unconfigured code, a refused switch,
the optional reset fallback, the single-instance lock, a busy channel, an
interrupted job, and the custom AT transport."""
import json
import os
import shutil
import unittest

from helpers import TOP, ShellTest

SW = TOP / 'root' / 'usr' / 'libexec' / 'simswitch' / 'switch'
AT = TOP / 'root' / 'usr' / 'libexec' / 'simswitch' / 'at'

UCI_SHOW = """\
simswitch.main=simswitch
simswitch.main.enabled='1'
simswitch.first=profile
simswitch.first.code='1111'
simswitch.first.label='Operator A'
simswitch.first.match='111111*,111111111111111'
simswitch.second=profile
simswitch.second.code='2222'
simswitch.second.label='Operator B'
simswitch.second.match='222222*,222222222222222'
"""

FAKE_AT = r'''
state=$STUBLOG/card
cur=$(cat "$state/iccid" 2>/dev/null)
mode=${FAKE_MODE:-normal}
cmd=$1
[ "$1" = "-t" ] && { shift 2; cmd=$1; }
case $mode in
    busy) exit 1 ;;
esac
case "$cmd" in
  'AT+CCID')        printf '+CCID: %s\r\nOK\r\n' "$cur" ;;
  'AT+CIMI')        case $cur in 2222*) printf '222222222222222\r\n' ;; *) printf '111111111111111\r\n' ;; esac ;;
  'AT+COPS?')       case $cur in 2222*) printf '+COPS: 0,0,"NETWORK B",7\r\n' ;; *) printf '+COPS: 0,0,"NETWORK A",7\r\n' ;; esac ;;
  'AT+CPIN?')       printf '+CPIN: READY\r\nOK\r\n' ;;
  'AT+CLCK="SC",2') printf '+CLCK: 0\r\nOK\r\n' ;;
  'AT+CLCK="SC",1,"2222"')
      if [ "$mode" = badpin ]; then
          printf '+CME ERROR: 16\r\n'
      else
          [ "$mode" = fallback ] || printf '222222222222222222' > "$state/iccid"
          printf 'OK\r\n'
      fi ;;
  'AT+RESET')       printf '222222222222222222' > "$state/iccid"; printf 'OK\r\n' ;;
  *)                printf 'ERROR\r\n' ;;
esac
'''

UCI_STUB = r'''
case "$*" in
  "-q show simswitch") cat "$STUBLOG/uci-show" ;;
  "-q get simswitch.main.enabled") echo "${STUB_ENABLED:-1}" ;;
  "-q get simswitch.main.iface") echo "${STUB_IFACE:-wan}" ;;
  "-q get simswitch.main.redial") echo "${STUB_REDIAL:-1}" ;;
  "-q get simswitch.main.switch_command") printf '%s\n' "$STUB_SWITCH_CMD" ;;
  "-q get simswitch.main.reset_commands") printf '%s\n' "${STUB_RESET:-}" ;;
  "-q get simswitch.main.wait_refresh") echo 45 ;;
  "-q get simswitch.main.wait_join") echo 60 ;;
  "-q get simswitch.main.wait_wan") echo 60 ;;
  "-q get simswitch.main.cache_ttl") echo 120 ;;
  "-q get simswitch.main.at_backend") echo "${STUB_AT_BACKEND:-auto}" ;;
  "-q get simswitch.main.at_port") echo "${STUB_AT_PORT:-}" ;;
  "-q get simswitch.main.at_command") echo "${STUB_AT_COMMAND:-}" ;;
  "-q get simswitch."*)
      key=${3#simswitch.}
      sec=${key%.*}; opt=${key##*.}
      sed -n "s/^simswitch\.$sec\.$opt='\(.*\)'\$/\1/p" "$STUBLOG/uci-show" | head -n 1
      ;;
  *) exit 1 ;;
esac
'''


class SimSwitch(ShellTest):
    def setUp(self):
        super().setUp()
        self.card = self.tmp / 'card'
        self.card.mkdir()
        (self.card / 'iccid').write_text('111111111111111111')
        self.run_dir = self.tmp / 'run'
        (self.tmp / 'uci-show').write_text(UCI_SHOW)
        self.stub('uci', UCI_STUB)
        self.stub('logger', 'exit 0')
        self.stub('ifup', 'echo "$@" >> "$STUBLOG/ifup"')
        self.stub('ubus', r'''
case "$*" in
  "call network.interface.wan status") printf '{"up":true,"ipv4-address":[{"address":"10.0.0.2"}]}\n' ;;
  *) printf '{}\n' ;;
esac''')
        self.stub('jsonfilter', r'''
case "$*" in
  *"@.up"*) echo true ;;
  *"ipv4-address"*) echo 10.0.0.2 ;;
  *) echo '' ;;
esac''')
        self.stub('at-fake', FAKE_AT)

    def run_sim(self, shell, *args, **env):
        env.setdefault('SIMSWITCH_AT', str(self.stubs / 'at-fake'))
        env.setdefault('SIMSWITCH_RUN', str(self.run_dir))
        env.setdefault('SIMSWITCH_WAIT_REFRESH', '1')
        env.setdefault('SIMSWITCH_WAIT_JOIN', '1')
        env.setdefault('SIMSWITCH_WAIT_WAN', '1')
        env.setdefault('STUB_SWITCH_CMD', 'AT+CLCK="SC",1,"%s"')
        return self.script(shell, SW, *args, **env)

    def reset(self, iccid='111111111111111111'):
        (self.card / 'iccid').write_text(iccid)
        shutil.rmtree(self.run_dir, ignore_errors=True)

    def get(self, shell, **env):
        r = self.run_sim(shell, 'get', **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_get_reads_the_card(self):
        for shell in self.each_shell():
            d = self.get(shell)
            self.assertEqual(d['current']['code'], '1111')
            self.assertEqual(d['current']['name'], 'Operator A')
            self.assertEqual(d['current']['iccid'], '111111111111111111')
            self.assertEqual(d['current']['imsi'], '111111111111111')
            self.assertEqual(d['current']['sim'], 'READY')
            self.assertEqual([p['code'] for p in d['profiles']], ['1111', '2222'])
            self.assertEqual(d['configured'], 1)
            self.assertEqual(d['enabled'], 1)

    def test_switch_moves_to_the_other_profile(self):
        for shell in self.each_shell():
            self.reset()
            r = self.run_sim(shell, 'switch', '2222')
            log = (self.run_dir / 'log').read_text() if (self.run_dir / 'log').exists() else ''
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr + log)
            d = json.loads(r.stdout)
            self.assertEqual(d['phase'], 'done')
            self.assertEqual(d['to'], '2222')
            self.assertEqual(d['before'], '111111111111111111')
            self.assertEqual(d['after'], '222222222222222222')
            status = json.loads((self.run_dir / 'status.json').read_text())
            self.assertEqual(status['running'], 0)
            self.assertEqual(status['ok'], 1)
            self.assertEqual(status['data'], 1)
            self.assertEqual(self.get(shell)['current']['code'], '2222')

    def test_already_active_is_refused(self):
        for shell in self.each_shell():
            r = self.run_sim(shell, 'switch', '1111')
            self.assertEqual(r.returncode, 2)
            self.assertIn('already active', r.stderr)

    def test_unconfigured_code_is_refused(self):
        for shell in self.each_shell():
            r = self.run_sim(shell, 'switch', '3333')
            self.assertEqual(r.returncode, 2)
            self.assertIn('not configured', r.stderr)
            self.assertFalse((self.run_dir / 'status.json').exists())

    def test_refused_switch_reports_the_modem_error(self):
        for shell in self.each_shell():
            r = self.run_sim(shell, 'switch', '2222', FAKE_MODE='badpin')
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            d = json.loads(r.stdout)
            self.assertEqual(d['error'], 'The modem refused the switch')
            self.assertEqual(d['detail'], '+CME ERROR: 16')
            status = json.loads((self.run_dir / 'status.json').read_text())
            self.assertEqual(status['phase'], 'failed')
            self.assertEqual(status['ok'], 0)
            self.assertEqual(status['error'], 'The modem refused the switch')

    def test_reset_commands_when_the_sim_does_not_reload(self):
        for shell in self.each_shell():
            self.reset()
            r = self.run_sim(shell, 'switch', '2222', FAKE_MODE='fallback',
                             STUB_RESET='AT+RESET')
            log = (self.run_dir / 'log').read_text() if (self.run_dir / 'log').exists() else ''
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr + log)
            self.assertEqual(json.loads(r.stdout)['after'], '222222222222222222')
            self.assertIn('reset commands', log)

    def test_one_switch_at_a_time(self):
        for shell in self.each_shell():
            lock = self.run_dir / 'switch.lock'
            lock.mkdir(parents=True, exist_ok=True)
            (lock / 'pid').write_text(str(os.getpid()))
            r = self.run_sim(shell, 'switch', '2222')
            self.assertEqual(r.returncode, 3)
            self.assertIn('already running', r.stderr)

    def test_a_busy_channel_keeps_the_last_reading(self):
        for shell in self.each_shell():
            self.get(shell)
            d = self.get(shell, FAKE_MODE='busy')
            self.assertEqual(d['current']['iccid'], '111111111111111111')
            self.assertEqual((self.run_dir / 'state' / 'read_ok').read_text(), '0')

    def test_an_interrupted_job_is_reported(self):
        for shell in self.each_shell():
            self.run_dir.mkdir(parents=True, exist_ok=True)
            (self.run_dir / 'status.json').write_text('{"running":1,"ok":1,"phase":"sim_refresh"}')
            r = self.run_sim(shell, 'status')
            self.assertEqual(r.returncode, 0, r.stderr)
            d = json.loads(r.stdout)
            self.assertEqual(d['phase'], 'failed')
            self.assertEqual(d['error'], 'The switch was interrupted')

    def test_custom_at_transport(self):
        for shell in self.each_shell():
            self.stub('custom-at', r'''
printf '%s|%s|%s\n' "$1" "$2" "$3" >> "$STUBLOG/custom"
echo OK''')
            (self.tmp / 'custom').unlink(missing_ok=True)
            r = self.script(shell, AT, '-t', '5', 'AT+TEST',
                            STUB_AT_BACKEND='custom',
                            STUB_AT_COMMAND=str(self.stubs / 'custom-at'))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((self.tmp / 'custom').read_text().strip(), '-t|5|AT+TEST')

    def test_at_rejects_more_than_one_command(self):
        for shell in self.each_shell():
            r = self.script(shell, AT, 'AT+TEST\r',
                            STUB_AT_BACKEND='custom',
                            STUB_AT_COMMAND=str(self.stubs / 'custom-at'))
            self.assertEqual(r.returncode, 2)
            self.assertIn('one command per call', r.stderr)


if __name__ == '__main__':
    unittest.main()
