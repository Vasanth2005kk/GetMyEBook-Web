// awsAdminPanel.js — AJAX tests and toasts for AWS admin panel
(function ($) {
    'use strict';

    $(function () {
        var $form = $('#aws-cred-form');
        var $btnTest = $('#btn-aws-test');
        var $btnSave = $('#btn-aws-save');
        var $btnRemove = $('#btn-aws-remove');

        function getCsrfToken() {
            var t = $form.find('input[name="csrf_token"]');
            return t.length ? t.val() : '';
        }

        function showToast(message, type, subtitle) {
            type = type || 'success';
            var $container = $('#aws-toast-container');
            if (!$container.length) {
                $container = $('<div id="aws-toast-container" class="aws-toast-container" aria-live="polite" aria-atomic="true"></div>');
                $('body').append($container);
            }
            var $toast = $('<div class="aws-toast"></div>');
            $toast.addClass(type === 'error' ? 'error' : 'success');
            var html = '<div class="msg">' + message + '</div>' + (subtitle ? '<div class="sub">' + subtitle + '</div>' : '');
            $toast.html(html);
            $container.append($toast);
            // Force reflow then show
            window.getComputedStyle($toast[0]).opacity;
            $toast.addClass('show');
            // Auto remove after 5s
            setTimeout(function () {
                $toast.removeClass('show');
                setTimeout(function () { $toast.remove(); }, 300);
            }, 5000);
            return $toast;
        }

        window.showToast = showToast;

        function postTestConnection(payload) {
            var headers = { 'Content-Type': 'application/json' };
            var csrf = getCsrfToken();
            if (csrf) { headers['X-CSRFToken'] = csrf; }
            return fetch('/admin/aws-s3/test-connection', {
                method: 'POST',
                credentials: 'same-origin',
                headers: headers,
                body: JSON.stringify(payload)
            }).then(function (resp) {
                return resp.json().then(function (data) {
                    return { status: resp.status, json: data };
                }).catch(function () {
                    return { status: resp.status, json: { success: resp.ok, message: resp.statusText || 'No response' } };
                });
            });
        }

        $btnTest.on('click', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            var payload = {
                aws_access_key_id: $.trim($('#aws_access_key_id').val() || ''),
                aws_secret_access_key: $.trim($('#aws_secret_access_key').val() || ''),
                default_region: $.trim($('#aws_default_region').val() || ''),
                bucket_name: $.trim($('#aws_bucket_name').val() || ''),
                default_output_format: $.trim($('#aws_default_output_format').val() || '')
            };
            postTestConnection(payload).then(function (r) {
                var ok = r.json && r.json.success;
                var msg = (r.json && r.json.message) || (ok ? 'Connection test succeeded.' : 'Connection test failed.');
                showToast(msg, ok ? 'success' : 'error');
            }).catch(function (err) {
                showToast('Error testing connection: ' + (err && err.message ? err.message : String(err)), 'error');
            });
        });

        $btnSave.on('click', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            var payload = {
                aws_access_key_id: $.trim($('#aws_access_key_id').val() || ''),
                aws_secret_access_key: $.trim($('#aws_secret_access_key').val() || ''),
                default_region: $.trim($('#aws_default_region').val() || ''),
                bucket_name: $.trim($('#aws_bucket_name').val() || ''),
                default_output_format: $.trim($('#aws_default_output_format').val() || '')
            };
            postTestConnection(payload).then(function (r) {
                var ok = r.json && r.json.success;
                if (ok) {
                    showToast(r.json.message || 'Connection verified — saving...', 'success');
                    // Use native submit via prototype in case form has a named field 'submit'
                    try {
                        HTMLFormElement.prototype.submit.call($form[0]);
                    } catch (e) {
                        // Fallback to dispatching a submit event
                        var ev = document.createEvent('Event'); ev.initEvent('submit', true, true); $form[0].dispatchEvent(ev);
                    }
                } else {
                    showToast(r.json.message || 'Connection test failed — not saved.', 'error');
                }
            }).catch(function (err) {
                showToast('Error testing connection: ' + (err && err.message ? err.message : String(err)), 'error');
            });
        });

        if ($btnRemove && $btnRemove.length) {
            $btnRemove.on('click', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                if (confirm('Are you sure you want to remove the stored AWS credentials?')) {
                    var delForm = document.getElementById('aws-delete-form');
                    if (delForm) { delForm.submit(); }
                }
            });
        }

        // --- S3 info panel population ---
        var s3Loading = document.getElementById('s3-info-loading');
        var s3Error = document.getElementById('s3-info-error');
        var s3Content = document.getElementById('s3-info-content');

        function formatBytes(bytes) {
            if (bytes === 0) return '0 B';
            var k = 1024, sizes = ['B','KB','MB','GB','TB','PB'];
            var i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        function formatNumber(n) {
            if (n === null || n === undefined) return '-';
            return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        }

        function showS3Error(msg) {
            if (s3Loading) s3Loading.style.display = 'none';
            if (s3Content) s3Content.style.display = 'none';
            if (s3Error) { s3Error.style.display = ''; s3Error.textContent = msg || s3Error.textContent; }
        }

        function showS3Content() {
            if (s3Loading) s3Loading.style.display = 'none';
            if (s3Error) s3Error.style.display = 'none';
            if (s3Content) s3Content.style.display = '';
        }

        function populateS3Info(data) {
            try {
                var bucket = data.bucket_name || '-';
                var totalObjects = (data.total_objects != null) ? formatNumber(data.total_objects) : '-';
                var used = (data.total_bytes != null) ? formatBytes(data.total_bytes) : '-';
                var storageLimit = (data.storage_limit_bytes != null) ? data.storage_limit_bytes : null;

                var bucketEl = document.getElementById('s3-bucket-name');
                var objsEl = document.getElementById('s3-total-objects');
                var usedEl = document.getElementById('s3-storage-used');
                var freeCard = document.getElementById('s3-free-storage-card');
                var freeEl = document.getElementById('s3-free-storage');
                var expEl = document.getElementById('s3-expiring');

                if (bucketEl) bucketEl.textContent = bucket;
                var objectsLabel = (window.AWS_S3_STRINGS && window.AWS_S3_STRINGS.objectsLabel) || 'Objects';
                if (objsEl) objsEl.textContent = totalObjects + ' ' + objectsLabel;
                if (usedEl) usedEl.textContent = used;

                if (storageLimit != null && !isNaN(storageLimit) && Number(storageLimit) > 0) {
                    var freeBytes = Math.max(0, Number(storageLimit) - (Number(data.total_bytes) || 0));
                    if (freeEl) freeEl.textContent = formatBytes(freeBytes) + ' / ' + formatBytes(Number(storageLimit));
                    if (freeCard) freeCard.style.display = '';
                } else {
                    if (freeEl) freeEl.textContent = '';
                    if (freeCard) freeCard.style.display = 'none';
                }

                if (expEl) {
                    var expCount = (data.expiring_count != null) ? data.expiring_count : (data.expiring_items ? data.expiring_items.length : 0);
                    var expLabel = (window.AWS_S3_STRINGS && window.AWS_S3_STRINGS.expiringObjectsLabel) || 'objects expiring soon';
                    expEl.textContent = (expCount || 0) + ' ' + expLabel;
                }

                showS3Content();
            } catch (e) {
                showS3Error('Error rendering S3 information');
            }
        }

        // Fetch S3 info if credential present
        try {
            if (typeof window.AWS_CRED_ID === 'undefined' || window.AWS_CRED_ID === null) {
                // no credentials configured
                var noCredsMsg = (window.AWS_S3_STRINGS && window.AWS_S3_STRINGS.noCreds) || 'No AWS credentials configured.';
                showS3Error(noCredsMsg);
            } else {
                // Fetch information from backend endpoint. Backend should provide JSON:
                fetch('/admin/aws-s3/info', { credentials: 'same-origin' }).then(function (resp) {
                    if (!resp.ok) { throw new Error(resp.status + ' ' + resp.statusText); }
                    return resp.json();
                }).then(function (json) {
                    populateS3Info(json);
                }).catch(function (err) {
                    var unableMsg = (window.AWS_S3_STRINGS && window.AWS_S3_STRINGS.unableToRetrieve) || 'Unable to retrieve S3 information.';
                    showS3Error(unableMsg);
                    console.error('S3 info fetch error', err);
                });
            }
        } catch (e) {
            var unexpectedMsg = (window.AWS_S3_STRINGS && window.AWS_S3_STRINGS.unexpectedError) || 'Unexpected error fetching S3 information.';
            showS3Error(unexpectedMsg);
        }

        // Upload storage status (are uploads mirrored to S3?) and library sync
        var $btnSync = $('#btn-aws-sync');

        function loadStorageStatus() {
            fetch('/admin/aws-s3/storage-status', { credentials: 'same-origin' }).then(function (resp) {
                return resp.json();
            }).then(function (json) {
                var count = 0, bytes = 0;
                $.each(json.stored_files || {}, function (_, v) { count += v.count; bytes += v.bytes; });
                $('#s3-storage-state').text(json.active
                    ? 'AWS S3 (' + json.source + ')'
                    : (json.enabled ? 'Local only (S3 not configured)'
                        : (json.admin_enabled === false ? 'Local library folder (switched off)'
                            : 'Local only (disabled by AWS_S3_ENABLED)')));
                $('#s3-stored-count').text(formatNumber(count) + ' (' + formatBytes(bytes) + ')');
                $btnSync.prop('disabled', !json.active);
            }).catch(function (err) {
                $('#s3-storage-state').text('-');
                console.error('Storage status fetch error', err);
            });
        }

        $btnSync.on('click', function () {
            var headers = { 'Content-Type': 'application/json' };
            var csrf = getCsrfToken();
            if (csrf) { headers['X-CSRFToken'] = csrf; }
            $btnSync.prop('disabled', true);
            fetch('/admin/aws-s3/sync', {
                method: 'POST', credentials: 'same-origin', headers: headers, body: '{}'
            }).then(function (resp) {
                return resp.json();
            }).then(function (json) {
                showToast($('<div>').text(json.message || '').html(), json.success ? 'success' : 'error');
            }).catch(function () {
                showToast('Failed to start library sync.', 'error');
            }).then(function () {
                $btnSync.prop('disabled', false);
            });
        });

        // Enable / disable switch: on = uploads stored in S3, off = local library folder only
        var $toggle = $('#aws-service-toggle');
        var strings = window.AWS_S3_STRINGS || {};

        function renderToggle(active) {
            $toggle.prop('checked', active);
            $('#aws-toggle-status').text(active ? (strings.enabled || 'Enabled') : (strings.disabled || 'Disabled'));
            $('#aws-toggle-hint').text(active
                ? (strings.storeS3 || 'New uploads are stored in AWS S3.')
                : (strings.storeLocal || 'New uploads are stored in the local library folder only.'));
        }

        $toggle.on('change', function () {
            var wanted = $toggle.is(':checked');
            var headers = { 'Content-Type': 'application/json' };
            var csrf = getCsrfToken();
            if (csrf) { headers['X-CSRFToken'] = csrf; }
            $toggle.prop('disabled', true);
            fetch('/admin/aws-s3/toggle', {
                method: 'POST', credentials: 'same-origin', headers: headers,
                body: JSON.stringify({ enabled: wanted })
            }).then(function (resp) {
                return resp.json().then(function (json) {
                    if (!resp.ok || !json.success) { throw new Error(json.message || resp.status); }
                    return json;
                });
            }).then(function (json) {
                renderToggle(json.aws_active);
                showToast($('<div>').text(json.aws_active
                    ? (strings.storeS3 || 'New uploads are stored in AWS S3.')
                    : (strings.storeLocal || 'New uploads are stored in the local library folder only.')).html(),
                    'success');
                loadStorageStatus();
            }).catch(function (err) {
                renderToggle(!wanted);
                showToast(strings.toggleFailed || 'Could not change the AWS S3 storage state.', 'error');
                console.error('AWS toggle error', err);
            }).then(function () {
                $toggle.prop('disabled', false);
            });
        });

        loadStorageStatus();

    });

})(jQuery);
