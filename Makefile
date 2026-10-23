include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-simswitch
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKGARCH:=all
# po2lmo, built by luci-base for the host
PKG_BUILD_DEPENDS:=luci-base/host

include $(INCLUDE_DIR)/package.mk

define Package/luci-app-simswitch
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=SIM profile switcher
  DEPENDS:=+luci-base +rpcd +ubus +jsonfilter +uci
endef

define Package/luci-app-simswitch/description
 Switch between the operator profiles stored on a SIM card from LuCI, the
 command line or UCI. The switch runs locally; no external service is used.
endef

define Package/luci-app-simswitch/conffiles
/etc/config/simswitch
endef

# LuCI names Chinese zh-cn / zh-tw (luci-languages.tsv); po2lmo writes no file
# for a catalog without translations (English: the msgids are the text).
SIMSWITCH_LMO_LANG=$(if $(filter zh_Hans,$(1)),zh-cn,$(if $(filter zh_Hant,$(1)),zh-tw,$(1)))

define Build/Compile
	mkdir -p $(PKG_BUILD_DIR)/lmo
	set -e; $(foreach po,$(wildcard $(CURDIR)/po/*/simswitch.po),$(STAGING_DIR_HOSTPKG)/bin/po2lmo $(po) $(PKG_BUILD_DIR)/lmo/simswitch.$(call SIMSWITCH_LMO_LANG,$(notdir $(patsubst %/,%,$(dir $(po))))).lmo;)
endef

define Package/luci-app-simswitch/install
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./root/etc/config/simswitch $(1)/etc/config/simswitch
	chmod 0600 $(1)/etc/config/simswitch

	$(INSTALL_DIR) $(1)/usr/libexec/simswitch
	$(INSTALL_BIN) ./root/usr/libexec/simswitch/at $(1)/usr/libexec/simswitch/at
	$(INSTALL_BIN) ./root/usr/libexec/simswitch/switch $(1)/usr/libexec/simswitch/switch

	$(INSTALL_DIR) $(1)/usr/libexec/rpcd
	$(INSTALL_BIN) ./root/usr/libexec/rpcd/simswitch $(1)/usr/libexec/rpcd/simswitch

	$(INSTALL_DIR) $(1)/usr/share/simswitch
	$(INSTALL_DATA) ./root/usr/share/simswitch/lib.sh $(1)/usr/share/simswitch/lib.sh

	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./root/usr/share/rpcd/acl.d/luci-app-simswitch.json $(1)/usr/share/rpcd/acl.d/luci-app-simswitch.json

	$(INSTALL_DIR) $(1)/usr/share/luci/menu.d
	$(INSTALL_DATA) ./root/usr/share/luci/menu.d/luci-app-simswitch.json $(1)/usr/share/luci/menu.d/luci-app-simswitch.json

	$(INSTALL_DIR) $(1)/www
	$(CP) ./htdocs/. $(1)/www/

	$(INSTALL_DIR) $(1)/usr/lib/lua/luci/i18n
	find $(PKG_BUILD_DIR)/lmo -name 'simswitch.*.lmo' -exec $(CP) {} $(1)/usr/lib/lua/luci/i18n/ \;

	$(INSTALL_DIR) $(1)/usr/bin
	$(LN) ../libexec/simswitch/switch $(1)/usr/bin/simswitch
endef

define Package/luci-app-simswitch/postinst
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	rm -f /tmp/luci-indexcache /tmp/luci-modulecache/* 2>/dev/null
	/etc/init.d/rpcd restart 2>/dev/null || true
}
exit 0
endef

define Package/luci-app-simswitch/postrm
#!/bin/sh
[ -n "$${IPKG_INSTROOT}" ] || {
	/etc/init.d/rpcd restart 2>/dev/null || true
}
exit 0
endef

$(eval $(call BuildPackage,luci-app-simswitch))
