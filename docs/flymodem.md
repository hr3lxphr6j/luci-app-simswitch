# Flymodem 运营商代码与 simswitch 配置

| code | 运营商 |
| --- | --- |
| `0200` | 中国移动 |
| `0100` | 中国联通 |
| `0300` | 中国电信 |

> 只使用卡或运营商提供的 code。不要猜测或随便填；错误的 code 可能导致 SIM 锁卡。

## `/etc/config/simswitch`

```uci
config simswitch 'main'
	option enabled '1'
	option iface 'wan'
	option redial '1'

	option at_backend 'custom'
	option at_command '/usr/libexec/unisoc-modem/at'
	option switch_command 'AT+CLCK="SC",1,"%s"'
	list reset_commands

	option wait_refresh '45'
	option wait_join '60'
	option wait_wan '60'
	option cache_ttl '120'

config profile 'mobile'
	option code '0200'
	option label 'China Mobile'
	option match '898600*,898602*,898604*,898607*,46000*,46002*,46004*,46007*,46008*'

config profile 'telecom'
	option code '0300'
	option label 'China Telecom'
	option match '898603*,898611*,46003*,46005*,46011*'
```

`0100` 只在卡确实支持联通 profile 时添加；双网卡不要启用。`at_command`
按你的固件的 AT 通道调整。
