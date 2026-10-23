#!/bin/sh
# Copy the package to a running OpenWrt device for testing. It does not switch
# anything: the last command only reads.
#
#   tools/deploy.sh root@192.168.1.1 [config]
#
# Without CONFIG, an existing /etc/config/simswitch is kept; the packaged
# default is installed only when the file is missing.

set -eu
HOST=${1:?usage: tools/deploy.sh user@host [config]}
CONF=${2:-}
DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

tar -cf - -C "$DIR/root" usr | ssh "$HOST" 'tar -xf - -C /'
tar -cf - -C "$DIR/htdocs" . | ssh "$HOST" 'tar -xf - -C /www'

if [ -n "$CONF" ]; then
    scp "$CONF" "$HOST:/etc/config/simswitch"
else
    scp "$DIR/root/etc/config/simswitch" "$HOST:/tmp/simswitch.conf"
    ssh "$HOST" 'if [ ! -f /etc/config/simswitch ]; then mv /tmp/simswitch.conf /etc/config/simswitch; fi; rm -f /tmp/simswitch.conf'
fi

PO2LMO=${PO2LMO:-$(command -v po2lmo 2>/dev/null || true)}
if [ -n "$PO2LMO" ]; then
    LMO=$(mktemp -d)
    for po in "$DIR"/po/*/simswitch.po; do
        lang=$(basename "$(dirname "$po")")
        case $lang in
            zh_Hans) code=zh-cn ;;
            zh_Hant) code=zh-tw ;;
            *) code=$lang ;;
        esac
        "$PO2LMO" "$po" "$LMO/simswitch.$code.lmo"
    done
    ssh "$HOST" 'mkdir -p /usr/lib/lua/luci/i18n'
    scp -q "$LMO"/simswitch.*.lmo "$HOST:/usr/lib/lua/luci/i18n/"
    rm -rf "$LMO"
else
    echo "po2lmo not found: leaving the installed catalogs as they are" >&2
fi

ssh "$HOST" '
    chown -R root:root /usr/libexec/simswitch /usr/share/simswitch \
        /usr/share/rpcd/acl.d/luci-app-simswitch.json \
        /usr/share/luci/menu.d/luci-app-simswitch.json \
        /www/luci-static/resources/view/simswitch
    chown root:root /usr/libexec/rpcd/simswitch /etc/config/simswitch
    chown root:root /usr/lib/lua/luci/i18n/simswitch.*.lmo 2>/dev/null || true
    chown -h root:root /usr/bin/simswitch 2>/dev/null || true
    chmod 0755 /usr/libexec/simswitch/at /usr/libexec/simswitch/switch /usr/libexec/rpcd/simswitch
    chmod 0600 /etc/config/simswitch
    ln -sf ../libexec/simswitch/switch /usr/bin/simswitch
    /etc/init.d/rpcd restart
    rm -f /tmp/luci-indexcache
    rm -f /tmp/luci-modulecache/*
    [ ! -f /lib/apk/db/installed ] || touch /lib/apk/db/installed
    simswitch get
'
