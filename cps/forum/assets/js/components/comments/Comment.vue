<template>
    <div :id="'comment-' + comment.id" class="comment-item d-flex mb-4 mt-1" :class="{'nested-reply': isReply}">
        <div class="flex-shrink-0 mr-3 comment-icon">
            <img :src="comment.owner.profile_picture" class="rounded-circle" :width="isReply ? 28 : 36" :height="isReply ? 28 : 36" style="object-fit: cover;">
        </div>
        <div class="flex-grow-1" style="min-width: 0;">
            <div class="d-flex align-items-baseline mb-1">
                <h6 class="font-weight-bold m-0 mr-2" style="font-size: 0.95rem;">
                    {{ comment.owner.name }}
                </h6>
                <span class="text-muted" style="font-size: 0.8rem;">
                    {{ postedAt }} 
                </span>
                 <!-- Push to right end -->
                <div class="position-relative ml-auto">
                    <span class="three-btn" @click="toggleMenu">
                        <i class="fa-solid fa-ellipsis-vertical"></i>
                    </span>
                    <div v-if="showMenu" class="dropdown-menu dropdown-menu-right show shadow-sm" style="top: 100%; right: 0; min-width: 120px; z-index: 1000; position: absolute;">
                        <template v-if="isOwner || isAdmin">
                            <button class="dropdown-item" @click="showEditionInput">
                                <i class="fas fa-pen mr-2"></i>Edit
                            </button>
                        </template>
                        <template v-if="isOwner || isAdmin">
                            <button class="dropdown-item text-danger" @click="deleteComment">
                                <i class="fas fa-trash mr-2"></i>Delete
                            </button>
                        </template>
                    </div>
                </div>
                <!-- Backbone for closing menu on outside click -->
                <div v-if="showMenu" @click="showMenu = false" class="fixed-inset" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 999; cursor: default;"></div>
            </div>
            
            <div class="comment-body">
                <!-- Quoted Parent Message -->
                <div v-if="parentComment" class="quoted-message mb-2 p-2 border-left-primary bg-light rounded-right" @click="scrollToParent" style="cursor: pointer;">
                    <div class="d-flex align-items-center mb-1">
                        <i class="fas fa-reply mr-2 text-primary small"></i>
                        <span class="small font-weight-bold text-dark">{{ parentComment.owner.name }}</span>
                    </div>
                    <div class="small text-muted text-line-clamp">
                        {{ parentComment.content }}
                    </div>
                </div>

                <textarea v-model="content" class="form-control mb-2" v-if="editing" rows="3"></textarea>
                <div v-else class="text-dark" style="font-size: 0.95rem; line-height: 1.5;" v-html="formattedContent">
                </div>
            </div>
            <div class="comment-actions mt-1 d-flex align-items-center"> 
                <div class="d-flex align-items-center mr-3">
                    <div class="like-wrapper d-flex align-items-center">
                        <div class="reaction-box">
                            <span class="reaction-icon" @click.stop="triggerReaction('like')" title="Like">👍</span>
                            <span class="reaction-icon" @click.stop="triggerReaction('celebrate')" title="Celebrate">👏</span>
                            <span class="reaction-icon" @click.stop="triggerReaction('support')" title="Support">🤝</span>
                            <span class="reaction-icon" @click.stop="triggerReaction('love')" title="Love">❤️</span>
                            <span class="reaction-icon" @click.stop="triggerReaction('insightful')" title="Insightful">💡</span>
                            <span class="reaction-icon" @click.stop="triggerReaction('funny')" title="Funny">😂</span>
                        </div>
                        
                        <button class="like-btn btn-link btn-sm p-0 text-muted font-weight-bold" @click="toggleLike" style="text-decoration: none; font-size: 0.9rem;">
                            <span :class="{'text-primary': liked && reactionType === 'like', 'text-success': liked && reactionType === 'celebrate', 'text-warning': liked && (reactionType === 'support' || reactionType === 'insightful'), 'text-danger': liked && reactionType === 'love', 'text-info': liked && reactionType === 'funny'}">
                                {{ reactionLabel }}
                            </span>
                        </button>
                    </div>

                    <span class="text-muted mx-2">&middot;</span>

                    <!-- Reaction Status (Icons + Count) -->
                    <div v-if="likesCount > 0" class="ml-2 d-flex align-items-center text-muted small" style="cursor: pointer;" @click="toggleLike">
                        <span class="mr-1">&middot;</span>
                        <div class="reaction-stack d-flex align-items-center">
                            <span v-if="liked" class="reaction-mini-icon" :class="reactionType">
                                <i :class="reactionIconClass"></i>
                            </span>
                            <!-- Show top reaction from others if I haven't liked it but others have -->
                            <span v-if="!liked && likesCount > 0 && topReaction" class="reaction-mini-icon" :class="topReaction">
                                <i :class="getIconClass(topReaction)"></i>
                            </span>
                            <!-- Fallback generic like if no top reaction info -->
                            <span v-if="!liked && likesCount > 0 && !topReaction" class="reaction-mini-icon like">
                                <i class="fas fa-thumbs-up"></i>
                            </span>
                            <!-- Stack effect if multiple -->
                            <!-- Stack effect if multiple -->
                            <span v-if="likesCount > 1" class="reaction-mini-icon" :class="topReaction || 'like'" style="margin-left: -6px;">
                                <i :class="getIconClass(topReaction || 'like')"></i>
                            </span>
                        </div>
                        <span class="ml-1">{{ likesCount }}</span>
                    </div>
                </div>
                <!-- Reply button with message icon -->
                    <button class="btn btn-link btn-sm p-0 reply-btn" @click="toggleReply" style="text-decoration: none; font-size: 0.9rem;">
                        <i class="far fa-comment-dots message-icon"></i>
                        <span class="reply-text">Reply</span>
                    </button>
                    
                <template v-if="isOwner || isAdmin">
                     <button class="btn btn-link btn-sm p-0 mr-3 text-primary" v-if="editing" @click="updateComment">
                        <small>Save</small>
                    </button>
                    <button class="btn btn-link btn-sm p-0 text-danger" v-if="editing" @click="hideEditionInput">
                        <small>Cancel</small>
                    </button>
                </template>
            </div>
            
        </div>
    </div>
</template>

<script>
    import axios from "axios";

    export default {
        name: 'Comment',
        props: [
            'comment',
            'users',
            'isReply',
            'threadId',
            'parentComment'
        ],
        data() {
            return {
                editing: false,
                showMenu: false,
                content: "",
                liked: false, 
                likesCount: 0,
                reactionType: 'like', // default
                topReaction: null,
                now: new Date()
            }
        },
        mounted() {
            // Debug: Log the full comment object to see what backend is actually sending
            console.log('Comment data:', this.comment);
            
            if (this.comment.likes_count !== undefined && this.comment.likes_count !== null) {
                this.likesCount = parseInt(this.comment.likes_count);
            }
            
            // First, check if current user has liked this comment
            if (this.comment.liked_by_current_user) {
                this.liked = true; 
                
                // IMPORTANT: Only set reaction type if user has actually liked the comment
                // Check various possible keys that backend might use
                const rType = this.comment.current_user_reaction 
                           || this.comment.reaction_type 
                           || this.comment.user_reaction 
                           || this.comment.reaction;
                
                if (rType && typeof rType === 'string') {
                    this.reactionType = rType;
                } else {
                    this.reactionType = 'like';
                }
            } else {
                this.liked = false;
                this.reactionType = 'like';
            }

            if (this.comment.top_reaction) {
                this.topReaction = this.comment.top_reaction;
            }

            this.timer = setInterval(() => {
                this.now = new Date();
            }, 1000);
        },
        destroyed() {
            clearInterval(this.timer);
        },
        methods: {
            getIconClass(type) {
                const map = {
                    'like': 'fas fa-thumbs-up',
                    'celebrate': 'fas fa-hands-clapping',
                    'support': 'fas fa-hand-holding-heart',
                    'love': 'fas fa-heart',
                    'insightful': 'fas fa-lightbulb',
                    'funny': 'fas fa-face-laugh-squint'
                };
                return map[type] || 'fas fa-thumbs-up';
            },
            triggerReaction(type) {
                // If clicking the same reaction type that's already active, do nothing
                if (this.liked && this.reactionType === type) {
                    return;
                }

                // Update the reaction type
                const oldReactionType = this.reactionType;
                this.reactionType = type;

                // If not liked yet, toggle like to add reaction
                if (!this.liked) {
                    this.toggleLike();
                } else {
                    // Update existing reaction without toggling count
                    axios.post(this.endpoint() + '/like', { 
                        reaction_type: this.reactionType,
                        type: this.reactionType,
                        reaction: this.reactionType
                    })
                    .catch(e => {
                        console.error('Error updating reaction:', e);
                        // Revert on error
                        this.reactionType = oldReactionType;
                    });
                }
            },
            toggleLike() {
                this.liked = !this.liked;
                
                // If unliking, reset type to default for next time
                if(!this.liked) {
                    this.reactionType = 'like';
                }

                this.likesCount += this.liked ? 1 : -1;
                
                const payload = { 
                    reaction_type: this.liked ? this.reactionType : null,
                    type: this.liked ? this.reactionType : null,
                    reaction: this.liked ? this.reactionType : null
                };
                
                axios.post(this.endpoint() + '/like', payload)
                    .catch(e => {
                        console.error('Error toggling like:', e);
                        // Revert on error
                        this.liked = !this.liked;
                        this.likesCount += this.liked ? 1 : -1;
                    });
            },
            escapeHtml(text) {
                const map = {
                    '&': '&amp;',
                    '<': '&lt;',
                    '>': '&gt;',
                    '"': '&quot;',
                    "'": '&#039;'
                };
                return text.replace(/[&<>"']/g, function(m) { return map[m]; });
            },
            escapeRegex(string) {
                return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            },
            endpoint() {
                return `/forum/api/comments/${this.comment.id}`;
            },
            deleteComment() {
                this.showMenu = false;
                if(!confirm("Are you sure you want to delete this comment?")) return;
                axios.delete(this.endpoint())
                    .then(() => {
                        this.$emit('delete', this.comment)
                    })
                    .catch(e => console.log(e))
            },
            showEditionInput() {
                this.showMenu = false;
                this.content = this.comment.content;
                this.editing = true;
            },
            hideEditionInput() {
                this.editing = false;
            },
            updateComment() {
                // optimistic update
                const oldContent = this.comment.content;

                if (oldContent ===  this.content && (this.content.trim().length) === 0 || !this.content.trim()) {
                    this.editing = false;
                    return;
                }
                else {
                    this.$emit('update', { ...this.comment, content: this.content });
                    this.editing = false;
                    axios.patch(this.endpoint(), { content: this.content })
                        .then(({data}) => {
                            this.$emit('update', data)
                        })
                        .catch(error => {
                            // revert
                            this.$emit('update', { ...this.comment, content: oldContent });
                            console.log(error)
                        });
                    }
            },
            toggleMenu() {
                this.showMenu = !this.showMenu;
            },
            toggleReply() {
                this.$emit('reply', this.comment);
            },
            // Legacy reply method if used by something else, redirected
            reply() {
                this.toggleReply();
            },
            scrollToParent() {
                if (!this.parentComment) return;
                const parentEl = document.getElementById('comment-' + this.parentComment.id);
                if (parentEl) {
                    parentEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    parentEl.classList.add('highlight-comment');
                    setTimeout(() => parentEl.classList.remove('highlight-comment'), 2000);
                }
            }
        },
        computed: {
            reactionLabel() {
                if (!this.liked) return 'Like';
                const map = {
                    'like': 'Like',
                    'celebrate': 'Celebrate',
                    'support': 'Support',
                    'love': 'Love',
                    'insightful': 'Insightful',
                    'funny': 'Funny'
                };
                return map[this.reactionType] || 'Like';
            },
            reactionIconClass() {
                const map = {
                    'like': 'fas fa-thumbs-up',
                    'celebrate': 'fas fa-hands-clapping',
                    'support': 'fas fa-hand-holding-heart',
                    'love': 'fas fa-heart',
                    'insightful': 'fas fa-lightbulb',
                    'funny': 'fas fa-face-laugh-squint'
                };
                return map[this.reactionType] || 'fas fa-thumbs-up';
            },
            postedAt() {
                if (!this.comment.created_at) return '';
                
                let dateStr = this.comment.created_at;
                if (typeof dateStr === 'string') {
                     // Standardize format slightly for browser parsing compatibility (replace space with T)
                     // Do NOT force UTC (Z) as server seems to return Local Time relative to server
                     dateStr = dateStr.replace(' ', 'T');
                }
                
                const date = new Date(dateStr);
                const seconds = Math.floor((this.now - date) / 1000);
                
                if (seconds < 0) return "0s";

                let interval = seconds / 31536000;
                if (interval >= 1) return Math.floor(interval) + "y";
                
                interval = seconds / 2592000;
                if (interval >= 1) return Math.floor(interval) + "mo";
                
                interval = seconds / 86400;
                if (interval >= 1) return Math.floor(interval) + "d";
                
                interval = seconds / 3600;
                if (interval >= 1) return Math.floor(interval) + "h";
                
                interval = seconds / 60;
                if (interval >= 1) return Math.floor(interval) + "m";
                
                return Math.floor(seconds) + "s";
            },
            isOwner() {
                return !! window.Auth && window.Auth.id == this.comment.user_id
            },
            isAdmin() {
                return !! window.Auth && window.Auth.isAdmin;
            },
            formattedContent() {
                let content = this.escapeHtml(this.comment.content || "");
                if (!this.users || !this.users.length) return content;
                
                // Sort users by name length desc to prioritize longer names
                const sortedUsers = [...this.users].sort((a, b) => b.name.length - a.name.length);
                
                sortedUsers.forEach(user => {
                    const name = user.name;
                    // Match @Name
                    // strict matching to avoid partial replacements of same name if possible
                    // simple replace for now:
                    const escapedName = this.escapeRegex(name);
                    const regex = new RegExp(`@${escapedName}`, 'g');
                    content = content.replace(regex, `<span class="text-primary font-weight-bold">@${this.escapeHtml(name)}</span>`);
                });
                return content;
            },
            currentUserAvatar() {
                if (window.Auth && window.Auth.profile_picture) {
                    return window.Auth.profile_picture;
                }
                // Fallback to UI Avatars if user has name but no picture
                if (window.Auth && window.Auth.name) {
                    return `https://ui-avatars.com/api/?name=${encodeURIComponent(window.Auth.name)}&background=random&color=fff`;
                }
                // Generic fallback
                return 'https://www.gravatar.com/avatar/default?d=mp';
            },
            currentUserName() {
                return window.Auth ? window.Auth.name : 'Guest';
            },
            isLoggedIn() {
                return !!window.Auth;
            },
            canReply() {
                return !!window.Auth && window.Auth.email_verified;
            },
            hasReplies() {
                return this.comment.replies && this.comment.replies.length > 0;
            }
        }
    }
</script>

<style scoped>
    .three-btn {
        color: #6c757d !important;
        cursor: pointer;
        padding: 4px 8px;
    }

    .three-btn:hover {
        background-color: #f1f1f1;
        border-radius: 4px;
    }

    .like-btn {
        outline: 0;
        border: none;
        background-color:#FFFFFF;
    }
    /* Comment Item */
    .comment-item {
        transition: background-color 0.2s;
        border-bottom: 1px solid var(--border-color);
    }
    
    /* Remove border for nested replies */
    .comment-item.nested-reply {
        border-bottom: none;
        margin-bottom: 8px !important;
        margin-top: 8px !important;
    }

    .comment-item:last-child {
        border-bottom: none;
    }
    
    .comment-actions {
        transition: opacity 0.2s;
        display: flex;
        gap: 16px;
        padding-bottom: 0.2rem;
    }
    /* Reaction Picker Details */
    .like-wrapper {
        position: relative;
        display: inline-block;
    }

    .reaction-box {
        /* Hidden by default */
        visibility: hidden;
        opacity: 0;
        display: flex; /* Always layout as flex */
        align-items: center;
        
        position: absolute;
        bottom: 100%; /* Align to top of wrapper */
        left: -10px; 
        background-color: white;
        border-radius: 50px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.15);
        padding: 8px 16px;
        gap: 12px;
        z-index: 1000;
        margin-bottom: 12px; /* Visual gap */
        white-space: nowrap;
        border: 1px solid rgba(0,0,0,0.05);

        /* Smooth transition for showing/hiding */
        transform: translateY(10px) scale(0.9);
        transition: all 0.2s cubic-bezier(0.18, 0.89, 0.32, 1.28);
        transition-delay: 0.3s; /* Delay hiding to make it forgiving */
        pointer-events: none;
    }

    /* Invisible Bridge to cover the gap between button and box */
    .reaction-box::after {
        content: '';
        position: absolute;
        left: 0;
        width: 100%;
        bottom: -15px; /* Extend downwards to touch the button area */
        height: 20px;
        background: transparent;
    }

    /* Hover State */
    .like-wrapper:hover .reaction-box {
        visibility: visible;
        opacity: 1;
        transform: translateY(0) scale(1);
        transition-delay: 0s; /* Show immediately */
        pointer-events: auto;
    }

    .reaction-icon {
        font-size: 1.6rem;
        cursor: pointer;
        transition: transform 0.2s cubic-bezier(0.18, 0.89, 0.32, 1.28);
        user-select: none;
        line-height: 1;
    }

    .reaction-icon:hover {
        transform: scale(1.35) translateY(-4px);
    }
    
    /* Mini Icons in Status */
    .reaction-mini-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        color: white;
        font-size: 10px;
        border: 2px solid white; /* Overlap effect border */
    }
    
    /* Colors for Mini Icons */
    .reaction-mini-icon.like { background-color: #1b74e4; }
    .reaction-mini-icon.celebrate { background-color: #26a541; }
    .reaction-mini-icon.support { background-color: #7b68ee; }
    .reaction-mini-icon.love { background-color: #f02849; }
    .reaction-mini-icon.insightful { background-color: #e5a50a; }
    .reaction-mini-icon.funny { background-color: #1da1f2; }
/* 📱 Mobile Responsive */
    @media (max-width: 768px) {
        .comment-icon img{
            width: 30px;
            height: 30px;
            margin-top: 30%;
        }
        
        .comment-actions {
            gap: 12px;
        }
    }

    /* Quoted Message Styles */
    .quoted-message {
        background-color: #f8f9fa;
        border-radius: 4px;
        border-left: 4px solid #6366f1; /* Primary color */
    }

    .border-left-primary {
        border-left: 4px solid #6366f1;
    }
    
    .highlight-comment {
        background-color: rgba(99, 102, 241, 0.1); /* Primary color with opacity */
        transition: background-color 0.5s ease;
    }

    .text-line-clamp {
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        text-overflow: ellipsis;
        word-break: break-word;
    }
</style>

    .reply-textarea {
        background: transparent;
        resize: none;
        box-shadow: none !important;
        font-size: 0.95rem;
    }
    .reply-textarea::placeholder {
        color: #888;
    }

    .action-icon {
        font-size: 1.25rem;
        color: #666;
        cursor: pointer;
        transition: color 0.2s;
    }
    .action-icon:hover {
        color: #333;
    }

    .animate-fade-in {
        animation: fadeIn 0.3s ease-out;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .gap-3 {
        gap: 1rem;
    }
    
    .login-prompt {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
        border: 1px dashed #dee2e6;
    }
    
    /* Reply Button with Message Icon */
    .reply-btn {
        color: #8e8e8e !important;
        font-weight: 600 !important;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        transition: color 0.2s ease;
    }
    
    .reply-btn:hover {
        color: #555 !important;
    }
    
    .message-icon {
        font-size: 0.95rem;
        stroke-width: 1.5;
    }
    
    .reply-text {
        font-weight: 600;
    }
    
    /* Reply Count Button */
    .reply-count-btn {
        color: #8e8e8e;
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
    }
    
    .reply-count-text {
        font-weight: 600;
        position: relative;
    }
    
    .reply-count-btn:hover .reply-count-text {
        color: #555;
        text-decoration: underline;
    }
    
    /* Smooth Expand/Collapse Animation for Replies */
    .replies-expand-enter-active,
    .replies-expand-leave-active {
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
    }
    
    .replies-expand-enter {
        max-height: 0;
        opacity: 0;
        transform: translateY(-10px);
    }
    
    .replies-expand-enter-to {
        max-height: 2000px;
        opacity: 1;
        transform: translateY(0);
    }
    
    .replies-expand-leave {
        max-height: 2000px;
        opacity: 1;
        transform: translateY(0);
    }
    
    .replies-expand-leave-to {
        max-height: 0;
        opacity: 0;
        transform: translateY(-10px);
    }
    
    /* Nested Reply Indentation - Desktop */
    .nested-reply {
        padding-left: 0;
        margin-top: 12px;
    }
    
    .replies-wrapper {
        position: relative;
        border-left: 2px solid #eef0f2; /* Vertical Thread Line */
        margin-left: 20px;
        padding-left: 16px;
        margin-top: 12px;
    }
    
    /* Highlight new replies briefly */
    @keyframes highlight {
        0% { background-color: rgba(0, 123, 255, 0.1); }
        100% { background-color: transparent; }
    }
    .new-reply {
        animation: highlight 3s ease-out;
    }

    /* Mobile Touch-Friendly Design - Reduced Indentation */
    @media (max-width: 768px) {
        .replies-wrapper {
            margin-left: 10px;
            padding-left: 10px;
            border-left-width: 2px;
        }
        
        .comment-icon img {
            width: 28px !important;
            height: 28px !important;
        }
        
        .reply-btn,
        .reply-count-btn {
            padding: 4px 8px !important;
            min-height: 44px; /* iOS recommended touch target */
        }
        
        .message-icon {
            font-size: 1.1rem;
        }
        
        .reply-text,
        .reply-count-text {
            font-size: 0.9rem;
        }
    }

</style>