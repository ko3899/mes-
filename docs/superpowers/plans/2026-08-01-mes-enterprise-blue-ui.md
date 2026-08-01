# MES Enterprise Blue UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 MES 管理后台重构为已确认的 B「精致企业蓝」界面，同时保留全部后端接口、数据库、权限和业务行为。

**Architecture:** 保持现有原生 HTML/CSS/JavaScript 与页面渲染函数，通过语义化应用骨架、集中式 CSS 设计令牌和少量状态类完成视觉升级。测试以 Node 内置测试运行器验证 DOM/CSS/渲染契约，以 Playwright 验证真实服务中的登录、导航、主题、弹窗和响应式行为。

**Tech Stack:** HTML5、CSS3、原生 JavaScript、ECharts 5.4.3、Node.js `node:test`、Python Playwright、现有 Flask 服务。

## Global Constraints

- 不修改后端接口、数据库结构、权限模型或业务语义。
- 保留现有页面路由、关键元素 ID、全局交互入口和已完成的安全修复。
- 不引入前端框架、大型 UI 组件库或运行时字体依赖。
- 桌面验收视口为 1366×768、1920×1080；响应式验收视口为 768×1024、390×844。
- 新增 UI 契约必须先观察失败，再实现通过；每个阶段运行相关测试并提交。
- 深色主题、键盘焦点、减少动效和移动侧栏属于交付范围。

---

## File Map

- `admin/index.html`：登录页、应用骨架、顶栏、侧栏容器、全局弹窗的语义结构。
- `admin/static/css/style.css`：唯一的设计令牌和共享视觉系统，覆盖所有现有业务页生成的通用类。
- `admin/static/js/app.js`：登录显示状态、侧栏开关、主题状态、共享确认/对比渲染。
- `admin/static/js/menu.js`：菜单分组标记、导航项结构、展开和活动状态。
- `admin/static/js/pages/home.js`：工作台语义布局、指标、图表、预警和快捷操作。
- `admin/static/js/crud.js`：列表页工具栏、导入/导出与分页的语义类，保留 CRUD 数据流。
- `admin/static/js/modal.js`：必填标记的语义类，保留表单生成和保存流程。
- `tests/admin_ui_design.test.js`：静态 DOM/CSS 契约与渲染函数测试。
- `tests/browser/admin_enterprise_blue_ui.cjs`：真实浏览器关键路径和截图验收。

### Task 1: Semantic login and application shell

**Files:**
- Create: `tests/admin_ui_design.test.js`
- Modify: `admin/index.html`
- Modify: `admin/static/js/app.js`
- Modify: `admin/static/css/style.css`

**Interfaces:**
- Consumes: existing IDs `loginPage`, `lu`, `lp`, `loginBtn`, `lerr`, `appPage`, `sideBar`, `toggleBtn`, `globalSearch`, `themeBtn`, `logoutBtn`, `pageContent`, `modal`.
- Produces: shell classes `login-layout`, `login-brand`, `login-panel`, `app-shell`, `sidebar-shell`, `topbar`, `topbar-actions`, `is-hidden`, and `sidebar-open`.

- [ ] **Step 1: Write the failing shell contract tests**

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (name) => fs.readFileSync(path.join(root, name), 'utf8');

test('login and app shell expose the enterprise-blue semantic structure', () => {
  const html = read('admin/index.html');
  assert.match(html, /class="login-layout"/);
  assert.match(html, /class="login-brand"/);
  assert.match(html, /class="login-panel"/);
  assert.match(html, /class="sidebar-shell"/);
  assert.match(html, /class="topbar"/);
  assert.match(html, /aria-label="切换侧栏"/);
  assert.doesNotMatch(html, /id="globalSearch"[^>]+style=/);
  assert.doesNotMatch(html, /id="notifBadge"[^>]+style=/);
});

test('the stylesheet defines the application geometry and semantic tokens', () => {
  const css = read('admin/static/css/style.css');
  for (const token of ['--navy-950', '--primary-600', '--surface', '--workspace', '--border-subtle']) {
    assert.match(css, new RegExp(token.replace('--', '\\\\-\\\\-')));
  }
  for (const selector of ['.app-shell', '.sidebar-shell', '.main-shell', '.topbar', '.content']) {
    assert.match(css, new RegExp(selector.replace('.', '\\\\.')));
  }
});
```

- [ ] **Step 2: Run the shell tests and observe the expected failure**

Run: `node --test tests/admin_ui_design.test.js`  
Expected: FAIL because `login-layout`, `sidebar-shell`, `topbar` and the new tokens do not exist.

- [ ] **Step 3: Implement the semantic shell without changing IDs**

Use this structure in `admin/index.html`:

```html
<section id="loginPage" class="login-layout">
  <div class="login-brand" aria-hidden="true">
    <div class="brand-lockup"><span class="brand-mark">M</span><span>MES 工厂管家</span></div>
    <div class="login-brand-copy"><p class="eyebrow">SMART MANUFACTURING</p><h1>让生产现场清晰、协同、可追溯</h1></div>
    <div class="capability-list"><span>生产协同</span><span>质量闭环</span><span>全程追溯</span></div>
  </div>
  <div class="login-panel">
    <div class="login-box">
      <p class="eyebrow">MES CONTROL CENTER</p><h2>欢迎回来</h2><p class="login-subtitle">登录工厂生产管理平台</p>
      <label for="lu">用户名</label><input id="lu" type="text" autocomplete="username" placeholder="请输入用户名" value="admin">
      <label for="lp">密码</label><input id="lp" type="password" autocomplete="current-password" placeholder="请输入密码" value="admin123">
      <button id="loginBtn" type="button">登录系统</button><div id="lerr" class="login-err" role="status"></div>
    </div>
  </div>
</section>
<div id="appPage" class="app-shell is-hidden">
  <aside class="sidebar-shell"><div class="sidebar-brand"><span class="brand-mark">M</span><span class="sidebar-brand-copy"><strong>MES</strong><small>工厂管家</small></span></div><nav id="sideBar" class="sidebar-nav"></nav></aside>
  <div class="main-shell">
    <header class="topbar"><div class="topbar-leading"><button class="toggle" id="toggleBtn" type="button" aria-label="切换侧栏" aria-expanded="true">&#9776;</button><div class="breadcrumb-block"><span class="eyebrow">MES / OPERATIONS</span><strong id="bread">工作台</strong></div></div><div class="topbar-actions"><label class="global-search"><span aria-hidden="true">⌕</span><input type="search" id="globalSearch" placeholder="搜索产品、工单、设备…"></label><button class="icon-button notification-button" type="button" aria-label="查看通知" onclick="goPage('notifications')">🔔<span id="notifBadge" class="notification-badge">0</span></button><button class="icon-button theme-toggle" id="themeBtn" type="button" onclick="toggleTheme()" aria-label="切换深色主题">🌙</button><button class="user" id="logoutBtn" type="button" aria-label="退出登录"><span class="avatar" id="uav">A</span><span id="uname">管理员</span></button></div></header>
    <main class="content" id="pageContent"></main>
  </div>
</div>
```

Update `doLogin()` and `doLogout()` in `admin/static/js/app.js` to toggle `is-hidden` instead of writing layout styles:

```js
function setAuthenticatedView(authenticated) {
    document.getElementById('loginPage').classList.toggle('is-hidden', authenticated);
    document.getElementById('appPage').classList.toggle('is-hidden', !authenticated);
}
```

Replace the stylesheet with the declared color tokens and minimum shell geometry before adding component decoration:

```css
:root {
  --navy-950:#0b1f3a; --navy-900:#102a4c; --primary-600:#2563eb;
  --primary-700:#1d4ed8; --surface:#fff; --workspace:#f3f6fa;
  --text-strong:#172033; --text-muted:#667085; --border-subtle:#e2e8f0;
  --success:#16845b; --warning:#b56a09; --danger:#cf3f4f;
  --sidebar-width:248px; --topbar-height:64px; --radius-card:12px;
}
.is-hidden{display:none!important}.app-shell{display:flex;width:100%;height:100dvh;background:var(--workspace)}
.sidebar-shell{width:var(--sidebar-width);display:flex;flex-direction:column;background:var(--navy-950);color:#fff}
.main-shell{min-width:0;flex:1;display:flex;flex-direction:column}.topbar{height:var(--topbar-height);display:flex;align-items:center;justify-content:space-between;background:var(--surface);border-bottom:1px solid var(--border-subtle)}
.content{flex:1;min-height:0;overflow:auto;padding:24px;background:var(--workspace)}
```

- [ ] **Step 4: Run focused and existing UI tests**

Run: `node --test tests/admin_ui_design.test.js tests/admin_ui_utils.test.js`  
Expected: PASS with no warnings or uncaught exceptions.

- [ ] **Step 5: Commit the shell**

```bash
git add tests/admin_ui_design.test.js admin/index.html admin/static/js/app.js admin/static/css/style.css
git commit -m "feat: rebuild admin login and app shell"
```

### Task 2: Navigation, shared components, and CRUD surfaces

**Files:**
- Modify: `tests/admin_ui_design.test.js`
- Modify: `admin/static/js/menu.js`
- Modify: `admin/static/js/app.js`
- Modify: `admin/static/js/crud.js`
- Modify: `admin/static/js/modal.js`
- Modify: `admin/static/css/style.css`

**Interfaces:**
- Consumes: `MENUS`, `openMenus`, `buildMenu()`, `goPage(key)`, `crudRender()`, `openModalSync()` and existing button/tag/table classes.
- Produces: `menu-group`, `menu-parent`, `menu-item`, `menu-label`, `sidebar-collapsed`, `sidebar-open`, `table-wrap`, `toolbar-actions`, `required-mark`, and state utility classes.

- [ ] **Step 1: Add failing navigation and component contracts**

Append tests that load `menu.js` in a VM and inspect rendered HTML:

```js
test('menu output exposes group, parent, child, and label hooks', () => {
  const source = read('admin/static/js/menu.js');
  assert.match(source, /menu-group/);
  assert.match(source, /menu-parent/);
  assert.match(source, /menu-item/);
  assert.match(source, /menu-label/);
});

test('shared component styles cover data-heavy business screens', () => {
  const css = read('admin/static/css/style.css');
  for (const selector of ['.card', '.toolbar', '.table-wrap', '.page', '.btn', '.tag', '.form-item', '.modal-mask', '.batch-bar']) {
    assert.match(css, new RegExp(selector.replace('.', '\\\\.')));
  }
  assert.match(css, /:focus-visible/);
});
```

- [ ] **Step 2: Run tests and observe missing semantic hooks**

Run: `node --test tests/admin_ui_design.test.js`  
Expected: FAIL on `menu-group`, `menu-parent`, `menu-item` or `table-wrap`.

- [ ] **Step 3: Add semantic menu markup and class-based sidebar behavior**

Render every expandable menu as one group and preserve escaped destinations:

```js
h += '<section class="menu-group" data-group="' + MESUI.escapeHtml(m.k) + '">';
h += '<button class="menu-parent" type="button" data-menu="' + MESUI.escapeHtml(m.k)
    + '" aria-expanded="' + (op ? 'true' : 'false') + '"><span class="menu-label">'
    + MESUI.escapeHtml(m.t) + '</span><span class="arr" aria-hidden="true">'
    + (op ? '&#8722;' : '&#43;') + '</span></button>';
h += '<div class="sub' + (op ? ' show' : '') + '" id="sub_' + MESUI.escapeHtml(m.k) + '">';
h += '<button class="menu-item" type="button" data-page="' + MESUI.escapeHtml(s.k) + '"><span class="menu-label">'
    + MESUI.escapeHtml(s.t) + '</span></button>';
```

In `app.js`, make the toggle add `sidebar-collapsed` on desktop and `sidebar-open` on narrow screens, and close the drawer after `goPage()` navigation. Preserve `toggleBtn` and `sideBar` IDs.

- [ ] **Step 4: Add shared component classes and remove core inline presentation**

Wrap CRUD tables with `<div class="table-wrap">`, change the action container to `toolbar-actions`, change orange button inline styles to `btn btn-orange`, and change modal required stars to `<span class="required-mark">*</span>`. Add CSS for buttons, tags, forms, tables, pagination, modal, batch bar, loading/empty states and semantic foreground utilities.

- [ ] **Step 5: Run all Node tests**

Run: `node --test tests/*.test.js`  
Expected: all existing 47 tests plus the new UI design tests PASS.

- [ ] **Step 6: Commit navigation and shared components**

```bash
git add tests/admin_ui_design.test.js admin/static/js/menu.js admin/static/js/app.js admin/static/js/crud.js admin/static/js/modal.js admin/static/css/style.css
git commit -m "feat: unify admin navigation and components"
```

### Task 3: Production command-center dashboard

**Files:**
- Modify: `tests/admin_ui_design.test.js`
- Modify: `admin/static/js/pages/home.js`
- Modify: `admin/static/css/style.css`

**Interfaces:**
- Consumes: `/api/dashboard`, `/api/dashboard/charts`, IDs `s1`–`s6`, `chartOutput`, `chartWO`, `chartEqp`, `chartWS`, `lowStock`, `overdueMaint`.
- Produces: `dashboard-hero`, `metrics-grid`, `metric-card`, `dashboard-grid`, `chart-card`, `alert-grid`, `quick-actions`, and theme-aware chart palette.

- [ ] **Step 1: Add failing dashboard structure tests**

```js
test('home renderer uses command-center sections without layout styles', () => {
  const source = read('admin/static/js/pages/home.js');
  for (const hook of ['dashboard-hero', 'metrics-grid', 'metric-card', 'dashboard-grid', 'alert-grid', 'quick-actions']) {
    assert.match(source, new RegExp(hook));
  }
  assert.doesNotMatch(source, /style="display:grid/);
  assert.doesNotMatch(source, /linear-gradient/);
});
```

- [ ] **Step 2: Run the dashboard test and observe failure**

Run: `node --test tests/admin_ui_design.test.js`  
Expected: FAIL because the current renderer uses `.stats`, `.stat`, `.quick-btns` and inline grids.

- [ ] **Step 3: Rebuild dashboard markup while retaining IDs and API calls**

Use one hero, six metric cards, a two-column chart grid, a two-column alert grid and compact action buttons. Metric values keep IDs `s1`–`s6`; chart and table containers keep all existing IDs. Escape low-stock and maintenance fields through `MESUI.escapeHtml()` before insertion.

```js
function dashboardText(value) {
    return MESUI.escapeHtml(value == null ? '' : String(value));
}

var chartColors = ['#2563eb', '#16845b', '#cf3f4f', '#b56a09', '#64748b'];
```

Set ECharts axis, legend, split-line and series colors from this palette, and retain the existing resize listener.

- [ ] **Step 4: Add dashboard CSS and responsive grids**

```css
.dashboard-hero{display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:20px}
.metrics-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px;margin-bottom:16px}
.metric-card{min-width:0;padding:18px;background:var(--surface);border:1px solid var(--border-subtle);border-radius:var(--radius-card)}
.dashboard-grid,.alert-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:16px}
.chart-frame{height:280px}.quick-actions{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
```

- [ ] **Step 5: Run focused and complete Node tests**

Run: `node --test tests/admin_ui_design.test.js tests/admin_ui_utils.test.js`  
Then: `node --test tests/*.test.js`  
Expected: PASS; existing XSS escaping tests remain green.

- [ ] **Step 6: Commit the dashboard**

```bash
git add tests/admin_ui_design.test.js admin/static/js/pages/home.js admin/static/css/style.css
git commit -m "feat: redesign MES production dashboard"
```

### Task 4: Dark theme, responsive behavior, and accessible motion

**Files:**
- Modify: `tests/admin_ui_design.test.js`
- Modify: `admin/static/css/style.css`
- Modify: `admin/static/js/app.js`

**Interfaces:**
- Consumes: `data-theme`, `toggleTheme()`, `loadTheme()`, `updateThemeIcon()` and application state classes.
- Produces: complete `[data-theme="dark"]` tokens, 1200px/768px responsive rules, drawer overlay behavior, `prefers-reduced-motion` handling and accessible labels.

- [ ] **Step 1: Add failing theme and responsive tests**

```js
test('dark and responsive contracts are complete', () => {
  const css = read('admin/static/css/style.css');
  assert.match(css, /\[data-theme="dark"\]/);
  assert.match(css, /@media\s*\(max-width:\s*1199px\)/);
  assert.match(css, /@media\s*\(max-width:\s*767px\)/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /sidebar-open/);
});
```

- [ ] **Step 2: Run the test and observe missing dark/responsive coverage**

Run: `node --test tests/admin_ui_design.test.js`  
Expected: FAIL until all four contracts are represented.

- [ ] **Step 3: Implement theme and responsive rules**

Define dark semantic tokens instead of per-component inversion. At 1199px allow a 76px collapsed rail; at 767px position the 248px sidebar as a translated drawer with a fixed overlay. Stack dashboard grids, keep tables scrollable, make modal width `min(680px, calc(100vw - 24px))`, and disable nonessential transitions under reduced motion.

Update `updateThemeIcon()` to set both text and `aria-label`, and make the sidebar toggle `aria-expanded` reflect drawer/collapsed state.

- [ ] **Step 4: Run UI and full Node tests**

Run: `node --test tests/admin_ui_design.test.js`  
Then: `node --test tests/*.test.js`  
Expected: PASS.

- [ ] **Step 5: Commit theme and responsiveness**

```bash
git add tests/admin_ui_design.test.js admin/static/css/style.css admin/static/js/app.js
git commit -m "feat: add responsive dark admin theme"
```

### Task 5: Automated browser acceptance

**Files:**
- Create: `tests/browser/admin_enterprise_blue_ui.cjs`
- Generated but ignored: `reports/ui/login-desktop.png`
- Generated but ignored: `reports/ui/dashboard-desktop.png`
- Generated but ignored: `reports/ui/dashboard-mobile.png`

**Interfaces:**
- Consumes: running service `http://127.0.0.1:8080/admin`, seeded administrator credentials `admin` / `admin123`.
- Produces: repeatable Playwright assertions and screenshots for the approved viewports.

- [ ] **Step 1: Confirm Playwright helper usage before writing the test**

Run: `python C:\Users\huang\.agents\skills\webapp-testing\scripts\with_server.py --help`  
Expected: usage text. The environment has no Python Playwright package, so use the bundled Node Playwright runtime and the installed Chrome/Edge executable without adding project dependencies.

- [ ] **Step 2: Create browser acceptance test**

```js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');
const executablePath = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].find((candidate) => fs.existsSync(candidate));

(async () => {
  const browser = await chromium.launch({headless: true, executablePath});
  const page = await browser.newPage({viewport: {width: 1366, height: 768}});
  const errors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto('http://127.0.0.1:8080/admin', {waitUntil: 'domcontentloaded'});
  await page.locator('#lu').fill('admin');
  await page.locator('#lp').fill('admin123');
  await page.locator('#loginBtn').click();
  await page.locator('.dashboard-hero').waitFor({state: 'visible'});
  assert.equal(await page.locator('.metric-card').count(), 6);
  await page.locator('#themeBtn').click();
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
  await page.setViewportSize({width: 390, height: 844});
  await page.locator('#toggleBtn').click();
  await page.waitForFunction(() => document.getElementById('appPage').classList.contains('sidebar-open'));
  assert.deepEqual(errors, []);
  await browser.close();
})();
```

- [ ] **Step 3: Run browser acceptance**

Run: `$env:NODE_PATH='C:\Users\huang\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'; & 'C:\Users\huang\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests\browser\admin_enterprise_blue_ui.cjs`
Expected: exit code 0 and three screenshots in `reports/ui/`.

- [ ] **Step 4: Inspect screenshots and correct visual defects test-first**

Inspect all three images. If a defect is structural or interactive, add a failing assertion to `tests/admin_ui_design.test.js` or the Playwright script, observe the failure, then correct CSS/JS and rerun. Acceptance requires no clipped login form, no sidebar/content overlap, readable metric values, scrollable mobile tables and visible modal actions.

- [ ] **Step 5: Commit browser coverage**

```bash
git add tests/browser/admin_enterprise_blue_ui.cjs
git commit -m "test: cover enterprise blue admin flows"
```

### Task 6: Full regression and delivery review

**Files:**
- Verify: all changed frontend and test files.

**Interfaces:**
- Consumes: all prior task outputs.
- Produces: clean regression evidence, clean worktree and review-ready commit series.

- [ ] **Step 1: Run JavaScript syntax checks**

Run: `Get-ChildItem admin/static/js -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }`  
Expected: exit code 0 with no syntax errors.

- [ ] **Step 2: Run all JavaScript tests**

Run: `node --test tests/*.test.js`  
Expected: all tests PASS.

- [ ] **Step 3: Run backend regression**

Run: `python -m pytest -q`  
Expected: all 339 or more tests PASS.

- [ ] **Step 4: Run Python compilation check**

Run: `python -m compileall -q backend tests`  
Expected: exit code 0.

- [ ] **Step 5: Review the complete diff**

Run: `git diff HEAD~5 --check` and `git status --short`  
Expected: no whitespace errors; only intentionally modified files are present.

- [ ] **Step 6: Perform final code review**

Use the `requesting-code-review` skill. Review preservation of DOM IDs, API routes, escaped dynamic values, mobile sidebar state, dark tokens, focus visibility and test evidence. Fix every confirmed issue through a new failing regression test before changing production code.

- [ ] **Step 7: Commit any review fixes and verify clean state**

```bash
git add admin tests
git commit -m "fix: close enterprise blue UI review gaps"
git status --short
```

Expected: final `git status --short` is empty when review produced changes; omit the empty commit when no fixes are needed.
