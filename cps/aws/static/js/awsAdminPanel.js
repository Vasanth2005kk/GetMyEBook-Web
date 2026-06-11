(function ($) {
    'use strict';
    var CRED_ID = window.AWS_CRED_ID || null;
    function getCsrf() {
        var el = document.querySelector('[name=csrf_token]');
        return el ? el.value : '';
    }

    function esc(str) {
        return String(str).replace(/[&<>"']/g, function (m) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
        });
    }

    function fmtBytes(b) {
        if (b < 1024) return b + ' B';
        if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
        return (b / 1048576).toFixed(1) + ' MB';
    }

    window.awsToggleService = function (enabled) {
        var $overlay  = $('#aws-disabled-overlay');
        var $content  = $('#aws-main-content');
        var $status   = $('#aws-toggle-status');
        var $wrapper  = $('.aws-toggle-wrapper');
        var toggleUrl = $wrapper.data('toggle-url') || '/admin/aws-s3/toggle';
        var csrf      = $wrapper.data('csrf') || getCsrf();

        /* Optimistic UI update */
        if (enabled) {
            $overlay.removeClass('show');
            $content.removeClass('blurred');
            $status.text('Active').css('color', '#FF9900');
        } else {
            $overlay.addClass('show');
            $content.addClass('blurred');
            $status.text('Paused').css('color', '#888');
        }

        /* Persist to database */
        $.ajax({
            url: toggleUrl,
            method: 'POST',
            contentType: 'application/json',
            headers: { 'X-CSRFToken': csrf },
            data: JSON.stringify({ enabled: enabled }),
            success: function (res) {
                if (!res.success) {
                    /* Revert optimistic UI on failure */
                    $('#aws-service-toggle').prop('checked', !enabled);
                    awsToggleService(!enabled);
                    return;
                }
                /* Update timestamps */
                if (res.aws_enabled_at) {
                    var $enRow = $('#aws-enabled-at').closest('div');
                    $('#aws-enabled-at').text(res.aws_enabled_at);
                    $enRow.show();
                }
                if (res.aws_disabled_at) {
                    var $disRow = $('#aws-disabled-at').closest('div');
                    $('#aws-disabled-at').text(res.aws_disabled_at);
                    $disRow.show();
                }
            },
            error: function () {
                /* Revert on network/server error */
                $('#aws-service-toggle').prop('checked', !enabled);
                awsToggleService(!enabled);
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
                                '<td class="text-muted" style="font-size:1.3rem;">—</td>' +
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
                            '<td class="text-muted" style="font-size:1.3rem;">' + esc(mod) + '</td>' +
                            '</tr>'
                        );
                    }
                });

                var html =
                    '<table class="table table-striped table-hover table-condensed" id="aws-file-table">' +
                    '<thead><tr>' +
                    '<th>Key / Path</th><th>Size</th><th>Last Modified</th>' +
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

    $(function () {
        /* The initial toggle state is set by the server via the 'checked' attribute.
           We only need to apply the visual overlay state on page load. */
        var isChecked = $('#aws-service-toggle').is(':checked');
        if (!isChecked) {
            $('#aws-disabled-overlay').addClass('show');
            $('#aws-main-content').addClass('blurred');
        }
        $('#aws-prefix-filter').on('keypress', function (e) {
            if (e.which === 13) awsLoadFiles();
        });
    });

})(jQuery);
