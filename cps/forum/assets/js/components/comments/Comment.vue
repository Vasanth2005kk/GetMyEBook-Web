<template>
    <div class="comment my-2">
        <div class="d-flex align-items-center">
            <img :src="comment.owner.profile_picture" class="rounded-circle mr-2" width="25">
            <h6 class="m-0">
                {{ comment.owner.name }}
                <span class="text-muted small ml-2" style="font-size: 0.8em;">{{ postedAt }}</span>
            </h6>
        </div>
        <div class="comment-content">
            <textarea v-model="content" class="form-control mb-2" v-show="editing"></textarea>
            <div v-if="! editing">
                {{ comment.content }}
            </div>

        </div>
        <div class="d-flex justify-content-end">
            <div class="d-flex" v-if="! editing">
                <button class="btn btn-light mr-2" @click="toggleLike" title="Like">
                     <i class="las la-thumbs-up" :class="{'text-primary': liked}"></i>
                     <span v-if="likesCount > 0" class="ml-1">{{ likesCount }}</span>
                </button>
                <button class="btn btn-light mr-2" v-show="isOwner" @click="showEditionInput" title="Edit">
                    <i class="las la-pencil-alt"></i>
                </button>
                <button class="btn btn-light " @click="deleteComment" v-show="isOwner" title="Delete">
                    <i class="las la-trash text-danger"></i>
                </button>
            </div>
            <div class="d-flex" v-if="editing">
                <button class="btn btn-light text-danger mr-2" v-show="isOwner" @click="hideEditionInput">
                    Cancel
                </button>
                <button class="btn btn-light text-primary" v-show="isOwner"
                    @click.prevent="updateComment"
                >
                    Save
                </button>
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
            // loose initialization if available in comment prop
            if (this.comment.likes_count) {
                this.likesCount = this.comment.likes_count;
            }
            if (this.comment.liked_by_current_user) {
                this.liked = this.comment.liked_by_current_user;
            }
            // Update time every minute
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
                this.$emit('update', { ...this.comment, content: this.content });
                this.editing = false;

                axios.patch(this.endpoint(), { content: this.content })
                    .then(({data}) => {
                        this.$emit('update', data)
                    })
                    .catch(error => console.log(error));
            },
            toggleLike() {
                // Optimistic update
                this.liked = !this.liked;
                this.likesCount += this.liked ? 1 : -1;
                
                // Call backend (dummy endpoint for now, will fail 404/405 until implemented)
                axios.post(this.endpoint() + '/like')
                    .catch(e => {
                        // Revert on error
                        this.liked = !this.liked;
                        this.likesCount += this.liked ? 1 : -1;
                        console.log("Like endpoint not implemented yet", e);
                    });
            }
        },
        computed: {
            postedAt() {
                if (!this.comment.created_at) return '';
                
                // Assume Server sends datetime in UTC. 
                // If the string is "YYYY-MM-DD HH:MM:SS", appending 'Z' forces JS to read it as UTC.
                let dateStr = this.comment.created_at;
                if (typeof dateStr === 'string' && !dateStr.endsWith('Z') && !dateStr.includes('+')) {
                    dateStr += 'Z';
                }
                
                const date = new Date(dateStr);
                const seconds = Math.floor((this.now - date) / 1000);
                
                // Handle clock skew (if client time is behind server time)
                if (seconds < 0) return "just now";

                let interval = seconds / 31536000;
                if (interval > 1) return Math.floor(interval) + " years ago";
                
                interval = seconds / 2592000;
                if (interval > 1) return Math.floor(interval) + " months ago";
                
                interval = seconds / 86400;
                if (interval > 1) return Math.floor(interval) + " days ago";
                
                interval = seconds / 3600;
                if (interval > 1) return Math.floor(interval) + " hours ago";
                
                interval = seconds / 60;
                if (interval > 1) return Math.floor(interval) + " minutes ago";
                
                return "just now";
            },
            isOwner() {
                return !! window.Auth && window.Auth.id === this.comment.owner.id
            }
        }
    }
</script>

<style>
    .comment {
        background: #fff;
        padding: 1rem
    }

    .comment-content {
        margin-top: .25rem;
        padding-left: 2rem;
    }
</style>