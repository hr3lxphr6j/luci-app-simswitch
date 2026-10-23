'use strict';
'require view';
'require dom';
'require rpc';
'require poll';
'require ui';

var callGet = rpc.declare({
	object: 'simswitch',
	method: 'get',
	expect: {}
});

var callSwitch = rpc.declare({
	object: 'simswitch',
	method: 'switch',
	params: [ 'code' ],
	expect: {}
});

function phaseText(phase) {
	switch (phase) {
	case 'request':       return _('Sending the request…');
	case 'sim_refresh':   return _('Waiting for the SIM to reload…');
	case 'stack_restart': return _('Restarting the modem interface…');
	case 'reattach':      return _('Waiting for the network…');
	case 'done':          return _('Done');
	case 'failed':        return _('Failed');
	default:              return _('Working…');
	}
}

function maskImsi(imsi) {
	if (!imsi || imsi.length < 9)
		return imsi || '-';
	return imsi.slice(0, 5) + '…' + imsi.slice(-4);
}

function errText(d) {
	var e = (d && d.error) || '';

	switch (e) {
	case 'The modem refused the switch':
		return _('The modem refused the switch');
	case 'The SIM did not reload; the card may not offer this profile':
		return _('The SIM did not reload; the card may not offer this profile');
	case 'The switch was interrupted':
		return _('The switch was interrupted');
	case 'A switch is already running':
		return _('A switch is already running');
	case 'The AT transport is not configured':
		return _('The AT transport is not configured');
	case 'This profile is already active':
		return _('This profile is already active');
	}

	return e || _('unknown reason');
}

return view.extend({
	load: function() {
		return L.resolveDefault(callGet(), {});
	},

	render: function(data) {
		var self = this;

		this.root = E('div', { 'class': 'cbi-section' });
		this.paint(data || {});

		poll.add(function() {
			return L.resolveDefault(callGet(), {}).then(function(d) {
				self.paint(d || {});
			});
		}, 3);

		return this.root;
	},

	paint: function(d) {
		var self = this;
		var cur = d.current || {};
		var job = d.job || {};
		var nodes = [];

		nodes.push(E('h2', {}, [ _('SIM profiles') ]));
		nodes.push(E('p', {}, [
			_('Switch between the operator profiles stored on the SIM card. The switch runs locally on the router.')
		]));

		if (d.ok !== 1) {
			nodes.push(E('div', { 'class': 'alert-message warning' }, [
				_('The switch backend is unavailable: %s').format(d.error || _('unknown reason'))
			]));
			dom.content(this.root, nodes);
			return;
		}

		if (d.configured !== 1) {
			nodes.push(E('div', { 'class': 'alert-message warning' }, [
				_('No profiles are configured. Add one or more profile sections to /etc/config/simswitch.')
			]));
			dom.content(this.root, nodes);
			return;
		}

		if (d.enabled !== 1) {
			nodes.push(E('div', { 'class': 'alert-message warning' }, [
				_('The switch is disabled in /etc/config/simswitch.')
			]));
		}

		nodes.push(E('div', { 'class': 'cbi-section' }, [
			E('h3', {}, [ _('Current profile') ]),
			E('div', { 'class': 'cbi-section-node' }, [
				E('p', {}, [
					_('Profile') + ': ' + (cur.name || cur.code || _('Unknown')) +
					(cur.code ? ' (' + cur.code + ')' : '')
				]),
				E('p', {}, [ 'ICCID: ' + (cur.iccid || '-') ]),
				E('p', {}, [ 'IMSI: ' + maskImsi(cur.imsi) ]),
				E('p', {}, [ _('Network') + ': ' + (cur.cops || '-') ]),
				E('p', {}, [ _('SIM state') + ': ' + (cur.sim || '-') ])
			])
		]));

		var running = (job.running === 1 || d.busy === 1);

		if (running) {
			nodes.push(E('div', { 'class': 'alert-message' }, [
				phaseText(job.phase) + (job.elapsed ? ' (' + job.elapsed + ' s)' : '')
			]));
		}
		else if (job.phase === 'done' && job.ok === 1) {
			nodes.push(E('div', { 'class': 'alert-message success' }, [
				_('Switched to %s in %s s.').format(job.code || '-', job.elapsed || 0) + ' ' +
				(job.data === 1 ? _('Mobile data is back.') : _('Mobile data has not come back yet.'))
			]));
		}
		else if (job.phase === 'failed') {
			nodes.push(E('div', { 'class': 'alert-message warning' }, [
				_('The switch failed: %s').format(errText(job))
			]));
		}

		var row = E('div', { 'style': 'display:flex;flex-wrap:wrap;gap:8px;margin:12px 0' });

		(d.profiles || []).forEach(function(p) {
			var active = (cur.code === p.code);
			var b = E('button', {
				'class': 'cbi-button ' + (active ? 'cbi-button-apply' : 'cbi-button-action'),
				'disabled': (running || active || d.enabled !== 1) ? '' : null
			}, [ p.label + ' (' + p.code + ')' ]);

			b.addEventListener('click', function() {
				self.confirmSwitch(p, b);
			});

			row.appendChild(b);
		});

		nodes.push(E('div', { 'class': 'cbi-section' }, [
			E('h3', {}, [ _('Available profiles') ]),
			row,
			E('p', { 'style': 'opacity:.75;font-size:.85rem' }, [
				_('Only configured profiles are shown. A wrong profile code can lock the SIM; use only codes provided by your operator.')
			])
		]));

		dom.content(this.root, nodes);
	},

	confirmSwitch: function(p, btn) {
		var self = this;

		ui.showModal(_('Switch to %s?').format(p.label), [
			E('p', {}, [
				_('The device will lose connectivity for 10–40 seconds while the modem registers on the new profile.')
			]),
			E('div', { 'class': 'right' }, [
				E('button', { 'class': 'btn', 'click': ui.hideModal }, [ _('Cancel') ]),
				E('button', {
					'class': 'cbi-button cbi-button-negative',
					'click': function() {
						ui.hideModal();
						btn.disabled = true;

						return L.resolveDefault(callSwitch(p.code), {}).then(function(r) {
							if (!r || r.ok !== 1) {
								ui.addNotification(null, E('p', {}, [
									_('The switch could not be started: %s').format(errText(r))
								]), 'error');
							}
						}).then(function() {
							return L.resolveDefault(callGet(), {}).then(function(d) {
								self.paint(d || {});
							});
						});
					}
				}, [ _('Switch') ])
			])
		]);
	},

	handleSaveApply: null,
	handleSave: null,
	handleReset: null
});
