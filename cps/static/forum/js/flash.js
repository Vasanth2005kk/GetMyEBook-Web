// Flash Message Auto-Dismiss and Close Functionality
function closeFlash(button) {
    const flashMessage = button.closest('.flash-message');
    flashMessage.classList.add('flash-hiding');
    setTimeout(() => {
        flashMessage.remove();
    }, 400); // Match the animation duration
}

// Auto-dismiss flash messages after 3 seconds
document.addEventListener('DOMContentLoaded', function () {
    console.log("DOM Loaded with new Flash Style");

    const flashMessages = document.querySelectorAll('.flash-message');

    flashMessages.forEach(function (message) {
        setTimeout(function () {
            if (message) {
                message.classList.add('flash-hiding');
                setTimeout(() => {
                    message.remove();
                }, 400);
            }
        }, 3000);
    });

});
