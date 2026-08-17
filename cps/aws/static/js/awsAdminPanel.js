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
    });

})(jQuery);
