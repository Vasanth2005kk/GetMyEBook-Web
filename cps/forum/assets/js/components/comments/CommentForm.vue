<template>
    <div class="chat-input-container bg-white border-top p-3">
        <form method="POST" @submit.prevent="handleSubmit" v-if="canComment" class="chat-form">
            <div class="input-group d-flex align-items-center" style="background: #fff; border: 1px solid #e0e0e0; border-radius: 24px; padding: 4px 8px 4px 16px; transition: border-color 0.2s;">
                <input 
                    type="text" 
                    class="form-control border-0 shadow-none p-0" 
                    placeholder="chat..." 
                    v-model="content" 
                    @keydown="clearInput('content')"
                    style="background: transparent;"
                >
                <div class="input-actions ml-2">
                    <button class="btn btn-sm rounded-circle d-flex align-items-center justify-content-center" :disabled="isSending" style="width: 32px; height: 32px; background: #e0e0e0; color: #666;" :class="{'bg-primary text-white': content.length > 0}">
                        <i class="las la-plus" v-if="!isSending"></i>
                        <i class="las la-circle-notch la-spin" v-else></i>
                    </button>
                </div>
            </div>
            <div class="text-danger small mt-1 pl-3" v-if="errors.has('content')">{{ errors.get("content")}}</div>
        </form>
        <div v-else class="text-center small text-muted">
            <span v-html="restrictionMessage"></span>
        </div>
    </div>
</template>

<script>
    import axios from "axios"
    import Errors from "../../utils/Errors";

    export default {
        props: {
            threadId: {
                type: Number,
                required: true
            }
        },
        data() {
            return {
                content: "",
                auth: window.Auth,
                errors: new Errors(),
                isSending: false
            }
        },
        methods: {
            handleSubmit() {
                if (!this.content.trim()) return;
                this.isSending = true;

                axios.post(`/forum/api/threads/${this.threadId}/comments`, {content: this.content})
                    .then(({data}) => {
                        this.content = "";
                        this.$emit('submit', data);
                    })
                    .catch(error => this.errors.record(error.response.data))
                    .finally(() => this.isSending = false)
            },
            clearInput(key) {
                if(this.errors.has(key)) {
                    this.errors.clear(key);
                }
            }
        },
        computed: {
            canComment() {
                return  !! window.Auth && window.Auth.email_verified;
            },
            restrictionMessage() {
                
                if(! window.Auth) {
                    return `
                        <a href="/login" class="text-primary">Login</a> to chat
                    `
                }

                if(! window.Auth.email_verified){
                    return `Verify email to chat`
                }

                return ""
            }
        }
    }
</script>

<style scoped>
    .input-group:focus-within {
        border-color: #aaa !important;
    }
    .form-control::placeholder {
        color: #999;
    }
</style>