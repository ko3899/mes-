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

    return {
        escapeHtml: escapeHtml,
        menuPage: menuPage,
        statusHtml: statusHtml,
        errorMessage: errorMessage
    };
});
