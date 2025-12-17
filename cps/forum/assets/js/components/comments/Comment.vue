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
            </div>
            
            <div class="comment-body">
                <textarea v-model="content" class="form-control mb-2" v-if="editing" rows="3"></textarea>
                <div v-else class="text-dark" style="font-size: 0.95rem; line-height: 1.5; white-space: pre-wrap;">
                    {{ comment.content }}
                </div>
            </div>

            <!-- Actions (Edit/Delete/Like) - kept minimal -->
            <div class="comment-actions mt-1 d-flex align-items-center">
                <button class="btn btn-link btn-sm p-0 mr-3 text-muted" @click="toggleLike" style="text-decoration: none;">
                    <i class="las la-thumbs-up" :class="{'text-primary': liked}"></i>
                    <span v-if="likesCount > 0" class="small">{{ likesCount }}</span>
                </button>
                
                <template v-if="isOwner">
                    <button class="btn btn-link btn-sm p-0 mr-3 text-muted" v-if="!editing" @click="showEditionInput">
                        <small>Edit</small>
                    </button>
                    <button class="btn btn-link btn-sm p-0 text-muted" v-if="!editing" @click="deleteComment">
                         <small>Delete</small>
                    </button>
                    
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
            }, 60000);
        },
        destroyed() {
            clearInterval(this.timer);
        },
        methods: {
            endpoint() {
                return `/forum/api/comments/${this.comment.id}`;
            },
            deleteComment() {
                if(!confirm("Are you sure you want to delete this comment?")) return;
                axios.delete(this.endpoint())
                    .then(() => {
                        this.$emit('delete', this.comment)
                    })
                    .catch(e => console.log(e))
            },
            showEditionInput() {
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
            }
        },
        computed: {
            postedAt() {
                if (!this.comment.created_at) return '';
                
                let dateStr = this.comment.created_at;
                if (typeof dateStr === 'string' && !dateStr.endsWith('Z') && !dateStr.includes('+')) {
                    dateStr += 'Z';
                }
                
                const date = new Date(dateStr);
                const seconds = Math.floor((this.now - date) / 1000);
                
                if (seconds < 0) return "now";

                let interval = seconds / 31536000;
                if (interval > 1) return Math.floor(interval) + "y";
                
                interval = seconds / 2592000;
                if (interval > 1) return Math.floor(interval) + "mo";
                
                interval = seconds / 86400;
                if (interval > 1) return Math.floor(interval) + "d";
                
                interval = seconds / 3600;
                if (interval > 1) return Math.floor(interval) + "h";
                
                interval = seconds / 60;
                if (interval > 1) return Math.floor(interval) + "m";
                
                return "now";
            },
            isOwner() {
                return !! window.Auth && window.Auth.id === this.comment.owner.id
            }
        }
    }
</script>

<style scoped>
    .comment-item {
        transition: background-color 0.2s;
    }
    .comment-actions {
        opacity: 0;
        transition: opacity 0.2s;
    }
    .comment-item:hover .comment-actions {
        opacity: 1;
    }
</style>