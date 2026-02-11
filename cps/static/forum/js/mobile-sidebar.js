// Mobile Sidebar Menu JavaScript
document.addEventListener('DOMContentLoaded', function () {
    const menuBtn = document.getElementById('menuBtn');
    const mobileSidebar = document.getElementById('mobileSidebar');
    const closeSidebar = document.getElementById('closeSidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const deleteThreadBtn = document.getElementById('deleteThreadBtn');
    const currentTimeElement = document.getElementById('currentTime');

    // Update time display
    function updateTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        });
        const dateString = now.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
        if (currentTimeElement) {
            currentTimeElement.textContent = `${timeString} - ${dateString}`;
        }
    }

    // Update time every second
    if (currentTimeElement) {
        updateTime();
        setInterval(updateTime, 1000);
    }

    // Open sidebar
    function openSidebar() {
        if (mobileSidebar && sidebarOverlay && menuBtn) {
            mobileSidebar.classList.add('active');
            sidebarOverlay.classList.add('active');
            menuBtn.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }

    // Close sidebar
    function closeSidebarMenu() {
        if (mobileSidebar && sidebarOverlay && menuBtn) {
            mobileSidebar.classList.remove('active');
            sidebarOverlay.classList.remove('active');
            menuBtn.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    // Event listeners
    if (menuBtn) {
        menuBtn.addEventListener('click', function () {
            if (mobileSidebar.classList.contains('active')) {
                closeSidebarMenu();
            } else {
                openSidebar();
            }
        });
    }

    if (closeSidebar) {
        closeSidebar.addEventListener('click', closeSidebarMenu);
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeSidebarMenu);
    }

    // Delete thread button handler
    if (deleteThreadBtn) {
        deleteThreadBtn.addEventListener('click', function () {
            if (confirm('Are you sure you want to delete this discussion? This action cannot be undone.')) {
                // Submit the delete form
                const deleteForm = document.querySelector('.form-delete');
                if (deleteForm) {
                    deleteForm.submit();
                }
            }
        });
    }

    // Close sidebar on escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && mobileSidebar && mobileSidebar.classList.contains('active')) {
            closeSidebarMenu();
        }
    });
});
