(function(root, factory) {
    var api = factory();
    root.MESUI = api;
    if(typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function menuPage(menu) {
        return menu.k;
    }

    function statusHtml(field, value) {
        var label = null;
        if(field && field.s) {
            field.s.forEach(function(option) {
                if(String(option.v) === String(value)) label = option.t;
            });
        }
        if(label == null) {
            var numeric = Number(value);
            label = numeric === 1 ? '启用' : (numeric === 0 ? '禁用' : '未知');
        }
        var cls = Number(value) === 1 ? 'tag-ok' : (Number(value) === 0 ? 'tag-draft' : 'tag-no');
        return '<span class="tag ' + cls + '">' + escapeHtml(label) + '</span>';
    }

    function errorMessage(error, fallback) {
        return error && error.message ? error.message : fallback;
    }

    function sortRows(rows, field, order, type) {
        var direction = String(order || 'ASC').toUpperCase() === 'DESC' ? -1 : 1;
        var kind = type || 'text';
        return (Array.isArray(rows) ? rows : []).slice().sort(function(a, b) {
            var av = a && a[field];
            var bv = b && b[field];
            var aEmpty = av == null || av === '';
            var bEmpty = bv == null || bv === '';
            if(aEmpty || bEmpty) return aEmpty === bEmpty ? 0 : (aEmpty ? 1 : -1);
            var left;
            var right;
            if(kind === 'number') {
                left = Number(av);
                right = Number(bv);
            } else if(kind === 'date') {
                left = Date.parse(av) || 0;
                right = Date.parse(bv) || 0;
            } else {
                left = String(av);
                right = String(bv);
            }
            var result = typeof left === 'string'
                ? left.localeCompare(right, 'zh-CN', {numeric: true, sensitivity: 'base'})
                : (left === right ? 0 : (left < right ? -1 : 1));
            return result * direction;
        });
    }

    function nextSortState(state, field) {
        var current = state || {};
        if(current.field !== field) return {field: field, order: 'ASC'};
        if(String(current.order).toUpperCase() === 'ASC') return {field: field, order: 'DESC'};
        return {field: '', order: ''};
    }

    function sortHeaderHtml(field, label, state) {
        var active = state && state.field === field;
        var order = active ? String(state.order || '').toUpperCase() : '';
        var aria = order === 'ASC' ? 'ascending' : (order === 'DESC' ? 'descending' : 'none');
        var arrow = order === 'ASC' ? ' ↑' : (order === 'DESC' ? ' ↓' : ' ↕');
        return '<th class="sortable" aria-sort="' + aria + '">' +
            '<button type="button" class="table-sort-button' + (active ? ' is-active' : '') +
            '" data-sort-field="' + escapeHtml(field) + '" aria-label="按' + escapeHtml(label) +
            '排序">' + escapeHtml(label) + '<span class="table-sort-arrow" aria-hidden="true">' + arrow +
            '</span></button></th>';
    }

    var manualOrderRegistry = {
        'prod/workorder': {tableKey: 'prod/workorder'},
        'prod/task': {tableKey: 'prod/task'},
        'prod/report': {tableKey: 'prod/report'},
        'prod/sales': {tableKey: 'prod/sales'},
        'prod/plan': {tableKey: 'prod/plan'},
        'base/workshop': {tableKey: 'base/workshop'},
        'base/process': {tableKey: 'base/process'},
        'base/product': {tableKey: 'base/product'},
        'base/bom': {tableKey: 'base/bom'},
        'base/defect': {tableKey: 'base/defect'},
        'base/unit': {tableKey: 'base/unit'},
        'base/route': {tableKey: 'base/route'},
        'base/supplier': {tableKey: 'base/supplier'},
        'base/customer': {tableKey: 'base/customer'},
        'inv/inbound': {tableKey: 'inv/inbound'},
        'inv/outbound': {tableKey: 'inv/outbound'},
        'inv/balance': {tableKey: 'inv/balance'},
        'qm/incoming': {tableKey: 'qm/incoming'},
        'qm/process': {tableKey: 'qm/process'},
        'qm/outgoing': {tableKey: 'qm/outgoing'},
        'eqp/ledger': {tableKey: 'eqp/ledger'},
        'eqp/repair': {tableKey: 'eqp/repair'},
        'eqp/maintenance': {tableKey: 'eqp/maintenance'},
        'eqp/check': {tableKey: 'eqp/check'},
        'tool/ledger': {tableKey: 'tool/ledger'},
        'tool/borrow': {tableKey: 'tool/borrow'},
        'sched/team': {tableKey: 'sched/team'},
        'sched/plan': {tableKey: 'sched/plan'},
        'sys/user': {tableKey: 'sys/user'},
        'sys/role': {tableKey: 'sys/role'},
        'sys/dept': {tableKey: 'sys/dept'},
        'sys/dict': {tableKey: 'sys/dict'},
        'doc/list': {tableKey: 'doc/list'},
        'notifications': {tableKey: 'notifications'}
    };
    Object.assign(manualOrderRegistry, {
        'warehouse/list': {tableKey: 'warehouse/list'},
        'warehouse/area': {tableKey: 'warehouse/area'},
        'warehouse/location': {tableKey: 'warehouse/location'},
        'warehouse/arrival': {tableKey: 'warehouse/arrival'},
        'warehouse/transaction': {tableKey: 'warehouse/transaction'},
        'qm/template': {tableKey: 'qm/template'},
        'eqp/check-project': {tableKey: 'eqp/check-project'},
        'sched/calendar': {tableKey: 'sched/calendar'},
        'process/station-config': {tableKey: 'process/station-config'},
        'process/flow': {tableKey: 'process/flow'},
        'process/record': {tableKey: 'process/record'},
        'process/material': {tableKey: 'process/material'},
        'process/box': {tableKey: 'process/box'},
        'process/lock': {tableKey: 'process/lock'},
        'process/defect': {tableKey: 'process/defect'},
        'process/exception': {tableKey: 'process/exception'},
        'stage/code': {tableKey: 'stage/code'},
        'stage/record': {tableKey: 'stage/record'},
        'prod/transfer': {tableKey: 'prod/transfer'},
        'prod/material': {tableKey: 'prod/material'},
        'prod/outsource': {tableKey: 'prod/outsource'},
        'prod/serial': {tableKey: 'prod/serial'},
        'prod/labor': {tableKey: 'prod/labor'},
        'prod/packing': {tableKey: 'prod/packing'},
        'site/workstation': {tableKey: 'site/workstation'},
        'site/andon': {tableKey: 'site/andon'},
        'site/rework': {tableKey: 'site/rework'},
        'qm/first': {tableKey: 'qm/first'},
        'qm/defect': {tableKey: 'qm/defect'},
        'qm/8d': {tableKey: 'qm/8d'},
        'qm/supplier-eval': {tableKey: 'qm/supplier-eval'},
        'qm/capa': {tableKey: 'qm/capa'},
        'qm/control-plan': {tableKey: 'qm/control-plan'},
        'qm/eco': {tableKey: 'qm/eco'},
        'eqp/mold': {tableKey: 'eqp/mold'},
        'eqp/fixture': {tableKey: 'eqp/fixture'},
        'util/energy': {tableKey: 'util/energy'},
        'util/environment': {tableKey: 'util/environment'},
        'hr/training': {tableKey: 'hr/training'},
        'hr/skill-matrix': {tableKey: 'hr/skill-matrix'},
        '5s/audit': {tableKey: '5s/audit'},
        'svc/complaint': {tableKey: 'svc/complaint'},
        'svc/return': {tableKey: 'svc/return'},
        'trace/batch': {tableKey: 'trace/batch'},
        'flow/def': {tableKey: 'flow/def'},
        'flow/instance': {tableKey: 'flow/instance'},
        'flow/pending': {tableKey: 'flow/pending'},
        'sys/log': {tableKey: 'sys/log'},
        'sys/login-log': {tableKey: 'sys/login-log'},
        'sys/config': {tableKey: 'sys/config'},
        'sys/announcement': {tableKey: 'sys/announcement'},
        'sys/ip-whitelist': {tableKey: 'sys/ip-whitelist'},
        'sys/print-template': {tableKey: 'sys/print-template'},
        'sys/notify-channel': {tableKey: 'sys/notify-channel'}
    });

    function canAdjustManualOrder(state) {
        return !(state && state.field && state.order);
    }

    function displayPosition(positions, recordId) {
        var value = positions && positions[String(recordId)];
        return value == null ? null : Number(value);
    }

    function orderRecordsByPosition(records, positions) {
        return (records || []).slice().sort(function(left, right) {
            var leftPosition = displayPosition(positions, left.id);
            var rightPosition = displayPosition(positions, right.id);
            if(leftPosition == null || rightPosition == null) {
                if(leftPosition == null && rightPosition == null) return 0;
                return leftPosition == null ? 1 : -1;
            }
            return leftPosition - rightPosition;
        });
    }

    function recordIdFromRow(row) {
        var stored = row.getAttribute('data-record-id');
        if(stored && /^\d+$/.test(stored)) return Number(stored);
        var cells = row.children || [];
        for(var index = 0; index < Math.min(cells.length, 2); index += 1) {
            var value = String(cells[index].textContent || '').trim();
            if(/^\d+$/.test(value)) return Number(value);
        }
        return null;
    }

    function displayIdCell(row) {
        var cells = row.children || [];
        if(!cells.length) return null;
        if(cells[0].querySelector && cells[0].querySelector('input[type="checkbox"]')) return cells[1] || null;
        return cells[0];
    }

    function actionCellFor(row, hasActionColumn) {
        if(hasActionColumn) return row.lastElementChild;
        var cell = document.createElement('td');
        cell.className = 'manual-order-action-cell';
        row.appendChild(cell);
        return cell;
    }

    function enableManualTableOrder(root, pageKey, state) {
        var config = manualOrderRegistry[pageKey];
        if(!config || !root || !root.querySelectorAll || typeof api !== 'function') return;
        root.querySelectorAll('table').forEach(function(table) {
            if(table.getAttribute('data-manual-order-state')) return;
            var header = table.querySelector('thead tr');
            var body = table.querySelector('tbody');
            if(!header || !body) return;
            var rows = Array.prototype.slice.call(body.querySelectorAll(':scope > tr'));
            var records = rows.map(function(row) {
                return {row: row, id: recordIdFromRow(row)};
            }).filter(function(item) { return item.id != null; });
            if(!records.length) return;
            var hasActionColumn = !!(header.lastElementChild && /操作/.test(header.lastElementChild.textContent || ''));
            table.setAttribute('data-manual-order-state', 'loading');
            api('/api/table-order/' + config.tableKey).then(function(response) {
                if(!response || response.code !== 0 || !response.data) {
                    table.removeAttribute('data-manual-order-state');
                    return;
                }
                var positions = response.data.positions || {};
                var total = Number(response.data.total || records.length);
                if(canAdjustManualOrder(state) && table.dataset.fieldSortActive !== 'true') {
                    records = orderRecordsByPosition(records, positions);
                    records.forEach(function(item) { body.appendChild(item.row); });
                }
                if(!hasActionColumn) {
                    var actionHeading = document.createElement('th');
                    actionHeading.className = 'manual-order-action-heading';
                    actionHeading.textContent = '调整';
                    header.appendChild(actionHeading);
                }
                records.forEach(function(item) {
                    item.row.setAttribute('data-record-id', String(item.id));
                    var position = displayPosition(positions, item.id);
                    var idCell = displayIdCell(item.row);
                    if(idCell && position != null) {
                        idCell.classList.add('display-id-cell');
                        idCell.textContent = String(position);
                        idCell.title = '排列 ID；真实数据库 ID 已隐藏且不会改变';
                    }
                    var actionCell = actionCellFor(item.row, hasActionColumn);
                    var controls = document.createElement('span');
                    controls.className = 'manual-order-actions';
                    var disabled = !canAdjustManualOrder(state) || table.dataset.fieldSortActive === 'true';
                    controls.innerHTML = '<button type="button" class="manual-order-step" data-direction="up" title="上移一位"' +
                        (disabled || position <= 1 ? ' disabled' : '') + '>↑</button>' +
                        '<button type="button" class="manual-order-step" data-direction="down" title="下移一位"' +
                        (disabled || position >= total ? ' disabled' : '') + '>↓</button>' +
                        '<button type="button" class="manual-order-move" title="移动到目标排列 ID"' +
                        (disabled ? ' disabled' : '') + '>移到</button>';
                    controls.querySelectorAll('.manual-order-step').forEach(function(button) {
                        button.addEventListener('click', function() {
                            stepTableRecord(config.tableKey, item.id, button.getAttribute('data-direction'));
                        });
                    });
                    controls.querySelector('.manual-order-move').addEventListener('click', function() {
                        moveTableRecord(config.tableKey, item.id, position, total);
                    });
                    actionCell.insertBefore(controls, actionCell.firstChild);
                });
                table.setAttribute('data-manual-order-state', 'ready');
            });
        });
    }

    function enableTableSorting(root) {
        if(!root || !root.querySelectorAll) return;
        root.querySelectorAll('table').forEach(function(table) {
            if(table.getAttribute('data-sort-enhanced') === 'true') return;
            var head = table.querySelector('thead tr');
            var body = table.querySelector('tbody');
            if(!head || !body || !head.children.length || !body.children.length) return;
            var state = {index: -1, order: ''};
            Array.prototype.forEach.call(head.children, function(th, index) {
                if(th.querySelector('input') || /操作|选择|顺序/i.test(th.textContent || '')) return;
                if(th.querySelector('[data-sort-field]')) return;
                var label = (th.textContent || '').trim();
                if(!label) return;
                var button = document.createElement('button');
                button.type = 'button';
                button.className = 'table-sort-button';
                button.textContent = label + ' ↕';
                button.setAttribute('aria-label', '按' + label + '排序');
                th.textContent = '';
                th.appendChild(button);
                button.addEventListener('click', function() {
                    state.order = state.index === index && state.order === 'ASC' ? 'DESC' :
                        (state.index === index && state.order === 'DESC' ? '' : 'ASC');
                    state.index = state.order ? index : -1;
                    table.dataset.fieldSortActive = state.order ? 'true' : 'false';
                    table.querySelectorAll('.manual-order-step,.manual-order-move').forEach(function(control) {
                        control.disabled = !!state.order;
                        control.title = state.order ? '请先恢复默认顺序再调整' : control.title;
                    });
                    Array.prototype.forEach.call(head.children, function(other) {
                        other.removeAttribute('aria-sort');
                        var b = other.querySelector('.table-sort-button');
                        if(b) b.classList.remove('is-active');
                    });
                    if(!state.order) {
                        button.textContent = label + ' ↕';
                        return;
                    }
                    th.setAttribute('aria-sort', state.order === 'ASC' ? 'ascending' : 'descending');
                    button.classList.add('is-active');
                    button.textContent = label + (state.order === 'ASC' ? ' ↑' : ' ↓');
                    var rows = Array.prototype.slice.call(body.querySelectorAll(':scope > tr'));
                    rows.sort(function(a, b) {
                        var av = (a.children[index] && a.children[index].textContent || '').trim();
                        var bv = (b.children[index] && b.children[index].textContent || '').trim();
                        var an = Number(av.replace(/,/g, ''));
                        var bn = Number(bv.replace(/,/g, ''));
                        var result = !isNaN(an) && !isNaN(bn) ? an - bn : av.localeCompare(bv, 'zh-CN', {numeric: true});
                        return state.order === 'ASC' ? result : -result;
                    });
                    rows.forEach(function(row) { body.appendChild(row); });
                });
            });
            table.setAttribute('data-sort-enhanced', 'true');
        });
    }

    return {
        escapeHtml: escapeHtml,
        menuPage: menuPage,
        statusHtml: statusHtml,
        errorMessage: errorMessage,
        sortRows: sortRows,
        nextSortState: nextSortState,
        sortHeaderHtml: sortHeaderHtml,
        enableTableSorting: enableTableSorting,
        manualOrderRegistry: manualOrderRegistry,
        canAdjustManualOrder: canAdjustManualOrder,
        displayPosition: displayPosition,
        orderRecordsByPosition: orderRecordsByPosition,
        enableManualTableOrder: enableManualTableOrder
    };
});
