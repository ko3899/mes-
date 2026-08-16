const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');


const root = path.resolve(__dirname, '..');


function source(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8');
}


test('pending approvals submit the task id instead of the instance id', () => {
  const js = source('admin/static/js/pages/flow_spc.js');
  assert.match(js, /flowApprove\('\+r2\.task_id\+'\)/);
  assert.match(js, /flowReject\('\+r2\.task_id\+'\)/);
  assert.doesNotMatch(js, /flowApprove\('\+r2\.id\+'\)/);
});


test('flow definition form collects explicit approvers instead of hard-coding user 1', () => {
  const js = source('admin/static/js/pages/flow_spc.js');
  assert.match(js, /api\('\/api\/sys\/user\/list\?size=100'\)/);
  assert.match(js, /flow-step-assignee/);
  assert.match(js, /steps:stepsPayload/);
  assert.doesNotMatch(js, /assignee\":1/);
});


test('rework UI persists disposition and exposes the controlled completion action', () => {
  const js = source('admin/static/js/pages/final1.js');
  assert.match(js, /disposition:document\.getElementById\('f_type'\)\.value/);
  assert.match(js, /rw\.disposition/);
  assert.match(js, /\/api\/site\/rework\/'\+id\+'\/complete/);
  assert.doesNotMatch(js, /rework_type:document\.getElementById\('f_type'\)\.value/);
});


test('repair UI uses explicit start and complete state transitions', () => {
  const js = source('admin/static/js/pages/more.js');
  assert.match(js, /\/api\/eqp\/repair\/'\+id\+'\/start/);
  assert.match(js, /\/api\/eqp\/repair\/'\+id\+'\/complete/);
  assert.match(js, /if\(r2\.status === 0\)/);
  assert.match(js, /if\(r2\.status === 1\)/);
  assert.match(js, /api\('\/api\/eqp\/ledger\/list'\)/);
  assert.match(js, /<select id=\"f_eqid\"/);
  assert.doesNotMatch(js, /<label>设备ID/);
});


test('notification polling stays idle while the admin page is signed out', () => {
  const notification = source('admin/static/js/notification.js');
  const api = source('admin/static/js/api.js');
  assert.match(notification, /if\(typeof curUser === 'undefined' \|\| !curUser\) return/);
  assert.match(notification, /if\(typeof curUser !== 'undefined' && curUser\) loadNotifications\(\)/);
  assert.match(api, /doLogout\(true\)/);
});


test('admin shell restores an existing server session after refresh', () => {
  const app = source('admin/static/js/app.js');
  const api = source('admin/static/js/api.js');
  assert.match(app, /api\('\/api\/user\/info', \{skipAuthRedirect:true\}\)/);
  assert.match(app, /function applyAuthenticatedUser\(user\)/);
  assert.match(app, /restoreSession\(\);/);
  assert.match(api, /!opts\.skipAuthRedirect/);
});


test('approval submission selects a pending workorder instead of accepting a raw id', () => {
  const js = source('admin/static/js/pages/flow_spc.js');
  assert.match(js, /api\('\/api\/prod\/workorder\/list\?size=100'\)/);
  assert.match(js, /Number\(workorder\.status\) === 0/);
  assert.match(js, /<select id=\"f_bid\" disabled>/);
  assert.doesNotMatch(js, /<input id=\"f_bid\" type=\"number\"/);
});


test('destructive equipment and maintenance actions surface service errors', () => {
  const business = source('admin/static/js/pages/business.js');
  const maintenance = source('admin/static/js/pages/more3.js');
  assert.match(business, /if\(r&&r\.code===0\) eqpLoad\(\); else alert/);
  assert.match(maintenance, /if\(r&&r\.code===0\) maintLoad\(\); else alert/);
});


test('site workflows enforce the required fields before submitting', () => {
  const site = source('admin/static/js/pages/final1.js');
  assert.match(site, /if\(!d\.workstation_id\) \{ alert\('请选择工位'\)/);
  assert.match(site, /if\(!d\.description\) \{ alert\('请填写安灯描述'\)/);
  assert.match(site, /if\(!d\.workorder_id\) \{ alert\('请选择工单'\)/);
  assert.match(site, /if\(!d\.reason\) \{ alert\('请填写原因'\)/);
  assert.match(site, /if\(r&&r\.code===0\)wsLoad\(\);else alert/);
});


test('maintenance execution is hidden for inactive plans', () => {
  const maintenance = source('admin/static/js/pages/more3.js');
  assert.match(maintenance, /r2\.status \? '<button class=\"btn btn-green btn-sm\" onclick=\"maintExec/);
});


test('workflow list renderers escape stored business text', () => {
  const files = [
    source('admin/static/js/notification.js'),
    source('admin/static/js/pages/flow_spc.js'),
    source('admin/static/js/pages/more.js'),
    source('admin/static/js/pages/more3.js'),
    source('admin/static/js/pages/final1.js'),
  ];
  files.forEach((js) => assert.match(js, /MESUI\.escapeHtml/));
});
