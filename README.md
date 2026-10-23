# luci-app-simswitch

OpenWrt / LuCI 的多 profile SIM 卡切换工具。

在一张卡内的多个运营商 profile 之间切换，本地运行，不需要移动端 App
或外部服务。

> 非官方项目，与任何设备、模组或 SIM 卡厂商无隶属关系。

---

## 功能

- 读取当前 profile：运营商名、ICCID、IMSI、当前注册网络、SIM 状态
- 在已配置的 profile 之间切换（LuCI / CLI / UCI）
- 后台任务：阶段进度、超时、失败原因
- 切换后自动重拨 WAN，等新地址出现才报告完成
- 支持多种 AT 通道：`atinout`、自定义命令
- 只使用配置中列出的 profile code；默认没有配置任何 profile

## 不做什么

- 不创建、下载、写入或修改 SIM profile
- 不管理套餐、计费、实名、设备绑定
- 不支持单 profile SIM、eSIM 下载、物理卡槽切换
- 不探测或猜测 profile code
- 不绕过运营商或设备厂商的任何策略

## 安全

- profile code 由用户在配置中提供
- 错误的 code 可能耗尽卡的有限尝试次数并导致 SIM 锁定；只使用运营商或
  发卡方提供的 code
- 默认没有配置任何 profile：未配置时不显示、不执行
- 不做自动重试；同一时间只允许一个切换任务
- 切换会断网 10–40 秒（模组重新注册 + WAN 重拨），属正常现象

## 从 Releases 安装

发布页：<https://github.com/hr3lxphr6j/luci-app-simswitch/releases>

GitHub Releases 同时提供 `.ipk`（opkg）和 `.apk`（apk）两个包。两者都是
`PKGARCH:=all`，与 CPU 架构无关；按固件的包管理器选一个即可。

| 固件 | 包 | 安装 |
| --- | --- | --- |
| OpenWrt 24.10 及更早（opkg） | `.ipk` | `opkg update && opkg install ./luci-app-simswitch_*.ipk` |
| OpenWrt 25.12 及更新（apk） | `.apk` | `apk update && apk add --allow-untrusted ./luci-app-simswitch-*.apk` |

本地包没有签名，所以 apk 需要 `--allow-untrusted`。依赖会从固件源解析；
如果固件没有 `luci-base`，先安装它。安装后刷新 LuCI，菜单在
**Cellular → SIM profiles**。

## 从源码编译

把本目录放进 OpenWrt 的 package feed，或在 OpenWrt SDK 的 `package/`
下建立指向本目录的链接，选中 `luci-app-simswitch` 编译安装。

运行时依赖：`luci-base`、`rpcd`、`ubus`、`jsonfilter`、`uci`。
`atinout` 只在 `at_backend` 为 `atinout`（或 `auto` 且没有自定义命令）时需要。

## 配置

配置文件是 `/etc/config/simswitch`（安装时权限 0600）。

```uci
config simswitch 'main'
	option enabled '1'
	option iface 'wan'
	option redial '1'

	option at_backend 'atinout'
	option at_port '/dev/ttyUSB2'
	# 或者用自定义传输：PROGRAM -t TIMEOUT COMMAND
	# option at_backend 'custom'
	# option at_command '/usr/libexec/simswitch/my-at'

	# 选择 profile 的命令；%s 会被替换成 code
	option switch_command 'YOUR_SELECT_COMMAND %s'

	# SIM 没有自行重新加载时执行的可选命令
	list reset_commands

	option wait_refresh '45'
	option wait_join '60'
	option wait_wan '60'
	option cache_ttl '120'

config profile 'first'
	option code 'YOUR_CODE'
	option label 'First operator'
	option match 'ICCID_OR_IMSI_PATTERN'

config profile 'second'
	option code 'YOUR_OTHER_CODE'
	option label 'Second operator'
	option match 'ICCID_OR_IMSI_PATTERN'
```

说明：

- `code` 必须是四位数字，且在 `profile` 里唯一。
- `match` 是可选的、逗号分隔的 glob 列表，用来从 ICCID / IMSI / 网络名
  判断当前 profile；不配置时当前 code 显示为未知。
- `switch_command` 必须包含 `%s`；命令通过 AT 通道发送。
- `at_command` 被调用为 `PROGRAM -t TIMEOUT COMMAND`；`at_port` 必须是
  `/dev/tty*` 或 `/dev/wwan*` 下的设备。
- `reset_commands` 只在不自动重新加载的模组上需要；命令之间会等待 2 秒。
- `iface` 是 WAN 接口名；`redial=0` 时切换后不重拨。

## CLI

```
simswitch get            # 当前 profile 与配置列表（JSON）
simswitch switch CODE    # 切换（同步，10–40 秒）
simswitch status         # 上一次切换的状态（JSON）
simswitch log [N]        # 切换日志，默认最后 40 行
```

CLI 与 LuCI 使用同一把锁：同一时间只允许一个切换。

## LuCI

菜单：**Cellular → SIM profiles**（`admin/modem/simswitch`）。

如果固件的 LuCI 没有 `admin/modem`（Cellular）分类，把菜单文件里的路径改成
`admin/network/simswitch` 即可。

页面显示当前 profile、ICCID、IMSI、注册网络和 SIM 状态；每个已配置的
profile 一个按钮。切换前有二次确认，切换期间显示阶段进度，完成后显示
耗时和移动数据是否恢复。

## 目录

```
root/etc/config/simswitch                    配置
root/usr/libexec/simswitch/at                AT 传输
root/usr/libexec/simswitch/switch            状态机与 CLI 实现
root/usr/libexec/rpcd/simswitch              rpcd 后端
root/usr/share/simswitch/lib.sh              共享函数
root/usr/share/rpcd/acl.d/...                ACL
root/usr/share/luci/menu.d/...               菜单
htdocs/luci-static/resources/view/simswitch/ LuCI 页面
po/                                          zh_Hans / zh_Hant 翻译
tests/                                       单元测试
tools/deploy.sh                              开发用部署脚本
.github/workflows/release.yml                CI：构建并在 Release 中发布 ipk/apk
```

## 测试

```
cd tests
python3 -m unittest discover -v
```

测试用假 AT 通道（`SIMSWITCH_AT`）和假 `uci`，覆盖读取、切换、拒绝、
错误 code、重载兜底、单实例锁和 AT 传输；另有 i18n 测试检查页面文案
是否全部有中文翻译、`%s` 占位符是否一致。

## 部署（开发）

```
tools/deploy.sh root@192.168.1.1
```

脚本只复制文件、修正权限、重启 `rpcd` 并刷新 LuCI 缓存；最后执行一次
`simswitch get`（只读），不会切换 profile。已有 `/etc/config/simswitch`
不会被覆盖；要替换配置就把配置文件作为第二个参数传入。

## 发布（CI）

推送 `v*` tag 时，`.github/workflows/release.yml` 会并行构建两个包，并把它们
和 `SHA256SUMS` 一起作为 GitHub Release 资产发布：

- `.ipk`：OpenWrt 24.10.4 SDK（x86/64，`PKGARCH:=all`）
- `.apk`：OpenWrt 25.12.5 SDK（x86/64，`PKGARCH:=all`）

tag 必须与 `Makefile` 里的 `PKG_VERSION` 一致：

```sh
git tag v0.1.0
git push origin main v0.1.0
```

`workflow_dispatch` 只构建并上传 Actions artifacts，不创建 Release；适合在
发版前验证构建。SDK 下载优先用 `downloads.openwrt.org`，失败时回退到清华
镜像；apk 构建在 25.12 SDK 不可用时回退到 snapshot SDK。

## 状态

- [x] 包骨架：adapter / rpcd / ACL / 菜单 / LuCI / CLI
- [x] 单元测试
- [x] 在真实设备上安装回归
- [x] i18n：zh_Hans / zh_Hant（页面跟随 LuCI 语言）
- [x] CI 打包：ipk + apk
- [x] 发布：v0.1.0

## 许可

待定。
