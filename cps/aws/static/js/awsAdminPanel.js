/* ============================================================
   awsAdminPanel.js  –  AWS S3 Admin Panel JavaScript
   Depends on: jQuery (already loaded globally by layout.html)
   ============================================================ */

(function ($) {
    'use strict';

    /* ── State ─────────────────────────────────────────────── */
    var CRED_ID = window.AWS_CRED_ID || null;

    /* ── Utility: CSRF token ────────────────────────────────── */
    function getCsrf() {
        var el = document.querySelector('[name=csrf_token]');
        return el ? el.value : '';
    }

    /* ── Utility: escape HTML ──────────────────────────────── */
    function esc(str) {
        return String(str).replace(/[&<>"']/g, function (m) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
        });
    }

    /* ── Utility: format bytes ─────────────────────────────── */
    function fmtBytes(b) {
        if (b < 1024) return b + ' B';
        if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
        return (b / 1048576).toFixed(1) + ' MB';
    }

    /* ── Show / hide status boxes ──────────────────────────── */
    function showStatus(boxId, success, msg) {
        var $box = $('#' + boxId);
        var iconHtml = success ? '<span class="icon icon-ok"></span>' : '<span class="icon icon-exclamation"></span>';
        $box
            .removeClass('success error show')
            .addClass('show ' + (success ? 'success' : 'error'))
            .html(iconHtml + ' ' + esc(msg));
    }

    function hideStatus(boxId) {
        $('#' + boxId).removeClass('show success error').html('');
    }

    /* ── Button loading state ───────────────────────────────── */
    function btnLoading($btn, label) {
        $btn.prop('disabled', true)
            .data('original', $btn.html())
            .html('<span class="aws-spinner"></span> ' + label);
    }
    function btnReset($btn) {
        $btn.prop('disabled', false).html($btn.data('original'));
    }

    /* ── Service Toggle Logic ─────────────────────────────────── */
    window.awsToggleService = function (enabled) {
        var $overlay = $('#aws-disabled-overlay');
        var $content = $('#aws-main-content');
        var $status = $('#aws-toggle-status');

        if (enabled) {
            $overlay.removeClass('show');
            $content.removeClass('blurred');
            $status.text('Active').css('color', '#FF9900');
        } else {
            $overlay.addClass('show');
            $content.addClass('blurred');
            $status.text('Paused').css('color', '#888');
        }
        localStorage.setItem('aws_s3_service_enabled', enabled);
    };

    /* ── Toggle edit form ───────────────────────────────────── */
    window.awsToggleEditForm = function () {
        var $card = $('#aws-cred-form-card');
        $card.slideToggle(200);
        hideStatus('aws-stored-status');
    };

    /* ── Collect form values ────────────────────────────────── */
    function getFormValues() {
        return {
            aws_access_key_id: $('#aws_access_key_id').val().trim(),
            aws_secret_access_key: $('#aws_secret_access_key').val().trim(),
            default_region: $('#aws_default_region').val(),
            default_output_format: $('#aws_default_output_format').val(),
            bucket_name: $('#aws_bucket_name').val().trim()
        };
    }

    /* ── Test connection (form values) ─────────────────────── */
    window.awsTestFormConnection = function () {
        var $btn = $('#btn-aws-test');
        btnLoading($btn, 'Testing…');
        hideStatus('aws-stored-status');

        $.ajax({
            url: '/admin/aws-s3/test-connection',
            method: 'POST',
            contentType: 'application/json',
            headers: { 'X-CSRFToken': getCsrf() },
            data: JSON.stringify(getFormValues()),
            success: function (res) {
                var extra = (res.details && res.details.account_id)
                    ? ' — Account: ' + res.details.account_id : '';
                showStatus('aws-stored-status', true, res.message + extra);
            },
            error: function (xhr) {
                var msg = (xhr.responseJSON && xhr.responseJSON.message) ? xhr.responseJSON.message : 'Connection failed.';
                showStatus('aws-stored-status', false, msg);
            },
            complete: function () { btnReset($btn); }
        });
    };

    /* ── Test stored connection ────────────────────────────── */
    window.awsTestStoredConnection = function () {
        var $btn = $('#btn-aws-stored-test');
        btnLoading($btn, 'Testing…');
        hideStatus('aws-stored-status');

        $.ajax({
            url: '/admin/aws-s3/test-connection',
            method: 'POST',
            contentType: 'application/json',
            headers: { 'X-CSRFToken': getCsrf() },
            data: JSON.stringify({}),
            success: function (res) {
                showStatus('aws-stored-status', true, res.message);
            },
            error: function (xhr) {
                var msg = (xhr.responseJSON && xhr.responseJSON.message) ? xhr.responseJSON.message : 'Test failed.';
                showStatus('aws-stored-status', false, msg);
            },
            complete: function () { btnReset($btn); }
        });
    };

    /* ── Save / Update credentials ──────────────────────────── */
    window.awsSaveCredentials = function () {
        var $btn = $('#btn-aws-save');
        btnLoading($btn, CRED_ID ? 'Updating…' : 'Saving…');
        hideStatus('aws-stored-status');

        var url = CRED_ID ? '/admin/aws-s3/credentials/' + CRED_ID : '/admin/aws-s3/credentials';
        var method = CRED_ID ? 'PUT' : 'POST';

        $.ajax({
            url: url,
            method: method,
            contentType: 'application/json',
            headers: { 'X-CSRFToken': getCsrf() },
            data: JSON.stringify(getFormValues()),
            success: function (res) {
                showStatus('aws-stored-status', true, res.message);
                setTimeout(function () { location.reload(); }, 1200);
            },
            error: function (xhr) {
                var msg = (xhr.responseJSON && xhr.responseJSON.message) ? xhr.responseJSON.message : 'Save failed.';
                showStatus('aws-stored-status', false, msg);
                btnReset($btn);
            }
        });
    };

    /* ── Disconnect stored credentials / disconnect service ───────────────── */
    window.awsDisconnect = function (id) {
        if (!confirm('Disconnect AWS S3 service?')) return;
        var $btn = $('#btn-aws-disconnect');
        btnLoading($btn, 'Disconnecting…');
        hideStatus('aws-stored-status');

        $.ajax({
            url: '/admin/aws-s3/disconnect',
            method: 'DELETE',
            contentType: 'application/json',
            headers: { 'X-CSRFToken': getCsrf() },
            data: JSON.stringify({ id: id }),
            success: function (res) {
                showStatus('aws-stored-status', true, res.message || 'Disconnected.');
                setTimeout(function () { location.reload(); }, 900);
            },
            error: function (xhr) {
                var msg = (xhr.responseJSON && xhr.responseJSON.message) ? xhr.responseJSON.message : 'Disconnect failed.';
                showStatus('aws-stored-status', false, msg);
                btnReset($btn);
            }
        });
    };

    /* ── Delete credentials ─────────────────────────────────── */
    window.awsDeleteCredentials = function (id) {
        if (!confirm('Are you sure you want to delete the stored AWS credentials?')) return;
        $.ajax({
            url: '/admin/aws-s3/credentials/' + id,
            method: 'DELETE',
            headers: { 'X-CSRFToken': getCsrf() },
            success: function () { location.reload(); },
            error: function (xhr) {
                var msg = (xhr.responseJSON && xhr.responseJSON.message) ? xhr.responseJSON.message : 'Delete failed.';
                showStatus('aws-stored-status', false, msg);
            }
        });
    };


    window.awsLoadFiles = function () {
        var prefix = $('#aws-prefix-filter').val() || '';
        var $container = $('#aws-file-browser');
        $container.html('<p class="text-muted"><span class="aws-spinner"></span> Loading files…</p>');

        $.ajax({
            url: '/admin/aws-s3/files',
            method: 'GET',
            /* Tell the server we want JSON so is_ajax detection works */
            headers: {
                'Accept': 'application/json',
                'X-CSRFToken': getCsrf()
            },
            data: { prefix: prefix, max_keys: 100 },
            dataType: 'json',
            success: function (res) {
                if (!res.success) {
                    $container.html('<p class="text-danger"><span class="icon icon-exclamation"></span> ' + esc(res.message || 'Unknown error') + '</p>');
                    return;
                }
                if (!res.files || !res.files.length) {
                    $container.html('<p class="text-muted">No files found' + (prefix ? ' for prefix "' + esc(prefix) + '"' : '') + '.</p>');
                    return;
                }

                /* Group top-level folders vs plain files */
                var seenFolders = {};
                var rows = [];
                res.files.forEach(function (f) {
                    var key = f.key || '';
                    var slashIdx = key.indexOf('/');
                    if (slashIdx !== -1 && slashIdx < key.length - 1) {
                        /* Object is inside a sub-folder — show folder row once */
                        var folder = key.substring(0, slashIdx + 1);
                        if (!seenFolders[folder]) {
                            seenFolders[folder] = true;
                            rows.push(
                                '<tr class="folder-row">' +
                                '<td class="key-col"><span class="icon icon-folder"></span> ' +
                                    '<a href="#" onclick="$(\'#aws-prefix-filter\').val(\'' + folder.replace(/'/g, "\\'") + '\'); awsLoadFiles(); return false;">' + esc(folder) + '</a>' +
                                '</td>' +
                                '<td class="size-col">—</td>' +
                                '<td class="text-muted" style="font-size:0.82rem;">—</td>' +
                                '<td></td>' +
                                '</tr>'
                            );
                        }
                    } else {
                        /* Plain file in current prefix */
                        var mod = (f.last_modified || '').replace('T', ' ').substring(0, 19);
                        var size = (typeof f.size === 'number') ? fmtBytes(f.size) : (f.size || '—');
                        rows.push(
                            '<tr>' +
                            '<td class="key-col" title="' + esc(key) + '">' + esc(key) + '</td>' +
                            '<td class="size-col">' + esc(size) + '</td>' +
                            '<td class="text-muted" style="font-size:0.82rem;">' + esc(mod) + '</td>' +
                            '<td>' +
                                '<a href="' + esc(f.url || '#') + '" target="_blank" class="btn btn-xs btn-default" title="Open">' +
                                    '<span class="icon icon-new-window"></span>' +
                                '</a> ' +
                                '<button class="btn btn-xs btn-danger" title="Delete" onclick="awsDeleteFile(' + JSON.stringify(key) + ')">' +
                                    '<span class="icon icon-trash"></span>' +
                                '</button>' +
                            '</td>' +
                            '</tr>'
                        );
                    }
                });

                var html =
                    '<table class="table table-striped table-hover table-condensed" id="aws-file-table">' +
                    '<thead><tr>' +
                    '<th>Key / Path</th><th>Size</th><th>Last Modified</th><th>Actions</th>' +
                    '</tr></thead>' +
                    '<tbody>' + rows.join('') + '</tbody>' +
                    '</table>';

                if (res.truncated) {
                    html += '<p class="text-muted" style="font-size:0.8rem;">Results truncated — refine your prefix filter to see more.</p>';
                }
                $container.html(html);
            },
            error: function (xhr) {
                var msg = (xhr.responseJSON && xhr.responseJSON.message) ? xhr.responseJSON.message : 'Failed to load files.';
                $container.html('<p class="text-danger"><span class="icon icon-exclamation"></span> ' + esc(msg) + '</p>');
            }
        });
    };

    /* ── Delete a single S3 file ────────────────────────────── */
    window.awsDeleteFile = function (key) {
        if (!confirm('Delete "' + key + '" from S3? This cannot be undone.')) return;
        $.ajax({
            url: '/admin/aws-s3/files',
            method: 'DELETE',
            contentType: 'application/json',
            headers: { 'X-CSRFToken': getCsrf() },
            data: JSON.stringify({ key: key }),
            success: function (res) {
                if (res.success) awsLoadFiles();
                else alert('Delete failed: ' + res.message);
            },
            error: function () { alert('Network error during delete.'); }
        });
    };

    /* ── DOM ready ──────────────────────────────────────────── */
    $(function () {
        /* Initialize Service Toggle State */
        var savedState = localStorage.getItem('aws_s3_service_enabled');
        if (savedState === 'false') {
            $('#aws-service-toggle').prop('checked', false);
            awsToggleService(false);
        }

        /* Credential form submission (progressive enhancement) */
        $('#aws-cred-form').on('submit', function (e) {
            e.preventDefault();
            awsSaveCredentials();
        });

        /* Enter key triggers file search */
        $('#aws-prefix-filter').on('keypress', function (e) {
            if (e.which === 13) awsLoadFiles();
        });
    });

})(jQuery);
