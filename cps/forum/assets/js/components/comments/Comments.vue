<template>
    <div>
        <div class="comments-list">
            <Comment v-for="comment in comments" :comment="comment" :key="comment.id"
                :users="mentionableUsers" :thread-id="id" :parent-comment="getParent(comment)"
                @delete="removeComment" @update="updateComment" @reply="handleReply"
            />
        </div>
        <CommentForm class="forum-chat-box" ref="commentForm" :threadId="id" :users="mentionableUsers" :replying-to="replyingTo" @submit="handleNewComment" @cancel-reply="cancelReply"/>
    </div>
</template>

<script>
import Comment from "./Comment.vue"
import CommentForm from "./CommentForm.vue"
import axios from "axios";

export default {
    components: {
        CommentForm, Comment
    },
    props: ['id'],
    data() {
        return {
            comments: [],
            replyingTo: null
        }
    },
    computed: {
        mentionableUsers() {
            const users = new Map();
            // Include current user for testing/self-mention
            if (window.Auth && window.Auth.id) {
                users.set(window.Auth.id, window.Auth);
            }
            this.comments.forEach(c => {
                if (c.owner && c.user_id) {
                    users.set(c.user_id, c.owner);
                }
            });
            return Array.from(users.values());
        }
    },
    mounted() {
        this.fetchComments();
    },
    methods: {
        fetchComments() {
             axios.get(`/forum/api/threads/${this.id}/comments`)
                .then(({data}) => {
                    this.comments = this.flattenComments(data);
                })
                .catch(err => console.error("Error fetching comments:", err));

        },
        flattenComments(comments) {
            let flat = [];
            comments.forEach(c => {
                flat.push(c);
                if (c.replies && c.replies.length > 0) {
                    flat = flat.concat(this.flattenComments(c.replies));
                }
            });
            // Sort by created_at to ensure chronological order
            return flat.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
        },
        getParent(comment) {
            if (!comment.parent_id) return null;
            return this.comments.find(c => c.id == comment.parent_id);
        },
        handleNewComment(comment) {
            this.comments.push(comment);
            this.replyingTo = null; // Clear reply state after sending
            // Scroll to bottom
            this.$nextTick(() => {
                const container = this.$el.querySelector('.comments-list');
                if(container) container.scrollTop = container.scrollHeight;
            });
        },
        removeComment(deletedComment) {
            this.comments = this.comments.filter((comment) => comment.id !== deletedComment.id);
        },
        updateComment(updatedComment) {
            this.comments = this.comments.map(comment => {
                if(updatedComment.id === comment.id) {
                    return updatedComment;
                }
                return comment
            })
        },
        handleReply(comment) {
            this.replyingTo = comment;
            const form = this.$refs.commentForm;
            if (form) {
                form.focusInput();
            }
        },
        cancelReply() {
            this.replyingTo = null;
        }
    },
}
</script>
<style scoped>
    .comments-list{
        padding: 2rem;
        margin-bottom: 3.4rem !important;

    }
    /* 📱 Mobile Responsive */
    @media (max-width: 768px) {
        .comments-list {
            padding: 0.5rem;
        }
        .forum-chat-box{
            min-height: 50px;
        }
    }

</style>