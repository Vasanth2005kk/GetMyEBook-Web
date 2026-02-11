# Discussion Forum - Book Integration Update

## Overview
The discussion forum has been enhanced with a split-screen layout that shows:
- **Left Panel (35%)**: Book reader with the actual book content
- **Right Panel (65%)**: Discussion feed with comments and sidebar widgets

## Features Implemented

### 1. **Split-Screen Layout**
- Clean, modern design with book reader on the left
- Discussion thread and comments in the center
- Sidebar with Top Contributors and Recent Discussions on the right

### 2. **Book-Thread Linking**
- Added `book_id` field to Thread model
- Threads can now be directly linked to books
- Book reader iframe embedded in discussion page

### 3. **Premium UI Design**
- Modern gradient effects and color schemes
- Smooth animations and hover effects
- Responsive design for all screen sizes
- Professional typography and spacing

### 4. **Discussion Features**
- User avatars and names
- Timestamps (formatted as "x minutes ago")
- Comment boxes with Reply, Like, and Report buttons (Vue.js components)
- Thread statistics (views, comments count)

### 5. **Sidebar Widgets**
- **Top Contributors**: Shows users with most comments
- **Recent Discussions**: Latest 5 discussions
- **Quick Stats**: Visual stats for current discussion

## Database Changes

A new column `book_id` has been added to the `forum_threads` table. This will be automatically created when you run the application for the first time with these changes.

If you need to manually add the column to an existing database:

```sql
ALTER TABLE forum_threads ADD COLUMN book_id INTEGER;
```

## Files Modified

1. **Model**: `cps/forum/database/models/thread.py`
   - Added `book_id` field

2. **Routes**: `cps/forum/apps/threads/routes.py`
   - Updated `show()` to fetch book data and sidebar widgets
   - Updated `create()` to handle book_id parameter
   - Updated `book_thread()` to use book_id for matching

3. **Templates**:
   - `cps/forum/apps/threads/templates/threads/show.html` - New split-screen layout
   - `cps/forum/apps/threads/templates/threads/create.html` - Added book_id hidden field

4. **CSS**: `cps/static/forum/css/discussion.css`
   - Comprehensive styles for the new layout
   - Modern, premium design system
   - Responsive breakpoints

## Usage

### Linking a Thread to a Book

When creating a thread from a book detail page, pass the `book_id` as a query parameter:

```python
url_for('threads.create', title=book.title, book_id=book.id)
```

### Accessing Book Discussion

Navigate to: `/forum/book/<book_id>` to view or create discussions for a specific book.

## Responsive Design

The layout adapts to different screen sizes:
- **Desktop (>1200px)**: Full split-screen with sidebar
- **Tablet (768px-1200px)**: Stacked layout (book on top, discussion below)
- **Mobile (<768px)**: Single column, optimized for touch

## Color Scheme

- **Primary**: Indigo (#6366f1)
- **Secondary**: Green (#10b981)
- **Danger**: Red (#ef4444)
- **Text**: Dark Gray (#1f2937)
- **Background**: Light Gray (#f9fafb)

## Next Steps

1. Run the application to create/update database tables
2. Create some test discussions linked to books
3. Test the split-screen view with different book formats (EPUB, PDF, TXT)
4. Customize colors/styling as needed

## Notes

- The book reader uses an iframe to embed the existing book reading functionality
- Only books with supported formats (EPUB, PDF, TXT) will show in the reader
- The Vue.js comments component handles all comment interactions
- Top contributors are calculated across all discussions
- Recent discussions show the latest 5 threads globally
