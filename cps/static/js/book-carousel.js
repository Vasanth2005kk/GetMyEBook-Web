// Book Carousel Fade-in/Fade-out Animation
document.addEventListener('DOMContentLoaded', function () {
    console.log('Book carousel script loaded - DOM ready');

    const carousel = document.getElementById('heroCarousel');
    if (!carousel) {
        console.log('Carousel not found - may not be visible on this page');
        return;
    }

    console.log('Carousel found!');
    const items = carousel.querySelectorAll('.book-carousel-item');
    console.log('Total carousel items found:', items.length);

    if (items.length === 0) {
        console.log('No carousel items found');
        return;
    }

    // Remove duplicates - we only need the first set
    const totalBooks = items.length / 2;
    console.log('Removing duplicates, keeping first', totalBooks, 'books');
    for (let i = totalBooks; i < items.length; i++) {
        items[i].remove();
    }

    const actualItems = carousel.querySelectorAll('.book-carousel-item');
    console.log('Actual items after removing duplicates:', actualItems.length);

    let currentIndex = 0;
    const displayDuration = 10000; // 10 seconds per book (for testing)
    const fadeDuration = 1000; // 1 second fade transition

    console.log('Setting up carousel items...');
    // Set up all items
    actualItems.forEach((item, index) => {
        // Clear any inline styles that might interfere
        item.style.position = '';
        item.style.left = '';
        item.style.top = '';
        item.style.width = '';
        item.style.display = ''; // Let CSS handle display
        item.style.opacity = ''; // Let CSS handle opacity
        item.style.transition = ''; // Let CSS handle transition

        if (index === 0) {
            item.classList.add('active');
            console.log('Book', index, 'set as active');
        } else {
            item.classList.remove('active');
        }
    });

    function showNextBook() {
        const currentItem = actualItems[currentIndex];
        console.log('=== Transitioning from book', currentIndex, '===');

        // Remove active class from current item
        currentItem.classList.remove('active');

        // Move to next item (loop back to start if at end)
        currentIndex = (currentIndex + 1) % actualItems.length;
        const nextItem = actualItems[currentIndex];

        console.log('=== Showing book', currentIndex, '===');

        // Add active class to next item
        nextItem.classList.add('active');
    }

    // Start the carousel
    console.log('✅ Starting carousel with', actualItems.length, 'books');
    console.log('Display duration:', displayDuration / 1000, 'seconds per book');
    console.log('Fade duration:', fadeDuration / 1000, 'seconds');
    setInterval(showNextBook, displayDuration);
});
