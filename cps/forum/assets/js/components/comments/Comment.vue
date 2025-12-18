<template>
    <div class="comment-item d-flex mb-3">
        <div class="flex-shrink-0 mr-3">
            <img :src="comment.owner.profile_picture" class="rounded-circle" width="36" height="36" style="object-fit: cover;">
        </div>
        <div class="flex-grow-1">
            <div class="d-flex align-items-baseline mb-1">
                <h6 class="font-weight-bold m-0 mr-2" style="font-size: 0.95rem;">
                    {{ comment.owner.name }}
                </h6>
                <span class="text-muted" style="font-size: 0.8rem;">{{ postedAt }}</span>
                 <!-- Push to right end -->
                <div class="position-relative ml-auto">
                    <span class="three-btn" @click="toggleMenu">
                        <i class="fa-solid fa-ellipsis-vertical"></i>
                    </span>
                    <div v-if="showMenu" class="dropdown-menu dropdown-menu-right show shadow-sm" style="top: 100%; right: 0; min-width: 120px; z-index: 1000; position: absolute;">
                        <button class="dropdown-item" @click="reply">
                            <i class="fas fa-reply mr-2"></i>Reply
                        </button>
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
                <textarea v-model="content" class="form-control mb-2" v-if="editing" rows="3"></textarea>
                <div v-else class="text-dark" style="font-size: 0.95rem; line-height: 1.5;">
                    {{ comment.content }}
                </div>
            </div>

            <!-- Actions (Edit/Delete/Like) - kept minimal -->
            <div class="comment-actions mt-1 d-flex align-items-center"> 
                <button class="like-btn btn-link btn-sm p-0 mr-3 text-muted" @click="toggleLike" style="text-decoration: none;font-size: 1.3rem;">
                    <i class="fas fa-thumbs-up" :class="{'text-primary': liked}"></i>
                    <span v-if="likesCount > 0" class="small">{{ likesCount }}</span>
                </button>
                
                <template v-if="isOwner || isAdmin">
                    <!-- Edit/Delete moved to menu -->
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
        props: [
            'comment'
        ],
        data() {
            return {
                editing: false,
                showMenu: false,
                content: "",
                liked: false, 
                likesCount: 0,
                now: new Date()
            }
        },
        mounted() {
            if (this.comment.likes_count) {
                this.likesCount = this.comment.likes_count;
            }
            if (this.comment.liked_by_current_user) {
                this.liked = this.comment.liked_by_current_user;
            }
            this.timer = setInterval(() => {
                this.now = new Date();
            }, 1000);
        },
        destroyed() {
            clearInterval(this.timer);
        },
        methods: {
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
            },
            toggleLike() {
                this.liked = !this.liked;
                this.likesCount += this.liked ? 1 : -1;
                
                axios.post(this.endpoint() + '/like')
                    .catch(e => {
                        this.liked = !this.liked;
                        this.likesCount += this.liked ? 1 : -1;
                    });
            },
            toggleMenu() {
                this.showMenu = !this.showMenu;
            },
            reply() {
                this.showMenu = false;
                this.$emit('reply', this.comment);
            }
        },
        computed: {
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
                return !! window.Auth && window.Auth.id === this.comment.user_id
            },
            isAdmin() {
                return !! window.Auth && window.Auth.isAdmin;
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

    .comment-item:last-child {
        border-bottom: none;
    }
    .comment-actions {
        transition: opacity 0.2s;
        display: flex;
        gap: 16px;
    }
    .comment-item:hover .comment-actions {
        opacity: 1;
    }
</style>