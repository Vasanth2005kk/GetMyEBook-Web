<template>
    <div>
        <div class="comments-list mb-2">
            <Comment v-for="comment in comments" :comment="comment" :key="comment.id"
                @delete="removeComment" @update="updateComment" @reply="handleReply"
            />
        </div>
        <CommentForm ref="commentForm" :threadId="id" @submit="handleNewComment"/>
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
            comments: []
        }
    },
    mounted() {
        this.fetchComments();
    },
    methods: {
        fetchComments() {
             axios.get(`/forum/api/threads/${this.id}/comments`)
                .then(({data}) => this.comments = data.reverse())
        
                console.log("all Comments :",this.comments)

        },
        handleNewComment(comment) {
            this.comments.push(comment)
        },
        removeComment(deletedComment) {
            this.comments = this.comments.filter((comment) => comment.id !== deletedComment.id);
        },
        updateComment(updatedComment) {
            this.comments = this.comments.map(comment => {
                if(updatedComment.id === comment.id) {
                    comment = updatedComment;
                }

                return comment
            })
        },
        handleReply(comment) {
            const form = this.$refs.commentForm;
            if (form) {
                // Populate with username and focus
                form.content = `@${comment.owner.name} `;
                form.focusInput();
            }
        }
    },
}
</script>