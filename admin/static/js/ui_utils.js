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

    function enableTableSorting(root) {
        if(!root || !root.querySelectorAll) return;
        root.querySelectorAll('table').forEach(function(table) {
            if(table.getAttribute('data-sort-enhanced') === 'true') return;
            var head = table.querySelector('thead tr');
            var body = table.querySelector('tbody');
            if(!head || !body || !head.children.length || !body.children.length) return;
            var state = {index: -1, order: ''};
            Array.prototype.forEach.call(head.children, function(th, index) {
                if(th.querySelector('input') || /操作|选择/i.test(th.textContent || '')) return;
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
        enableTableSorting: enableTableSorting
    };
});
