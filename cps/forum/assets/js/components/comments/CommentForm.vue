<template>
    <div class="chat-input-container">
    <form method="POST" @submit.prevent="handleSubmit" v-if="canComment" class="chat-form">
        <div class="chat-input-box">
            
            <!-- Left Icons -->
            <div class="chat-left-icons">
                <!-- <button type="button" class="icon-btn">
                    <i class="fa-solid fa-circle-plus"></i>
                </button> -->
                <button type="button" class="icon-btn">
                    <i class="fa-regular fa-face-smile"></i>
                </button>
                 <button type="button" class="icon-btn">
                    <i class="fa-solid fa-at"></i>
                 </button>
                
            </div>

            <!-- Input -->
            <input
                type="text"
                ref="input"
                class="chat-input"
                placeholder="Ask anything"
                v-model="content"
                @keydown="clearInput('content')"
            />

            <!-- Right Button -->
            <button
                class="chat-send-btn"
                :class="{
                    active: content.length > 0 && !isSending,
                    loading: isSending
                }"
                :disabled="isSending"
            >

                <i class="fa-solid fa-paper-plane" v-if="!isSending"></i>
                <i class="fa-solid fa-spinner fa-spin" v-if="isSending"></i>


            </button>

        </div>

        <div class="text-danger small mt-1 pl-3" v-if="errors.has('content')">
            {{ errors.get("content") }}
        </div>
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
            },
            focusInput() {
                this.$refs.input.focus();
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
    .chat-input-container {
    background: #fff;
    border-top: 1px solid #e5e7eb;
    padding: 12px;
}

.chat-input-box {
    display: flex;
    align-items: center;

    /* Size */
    width: 100%;
    min-height: 72px;            /* height increase */
    
    /* Inside spacing */
    padding: 10px 14px;          /* top/bottom | left/right */
    padding-left: 18px;          /* extra space for left buttons */
    padding-bottom: 12px;        /* bottom space */

    gap: 10px;

    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 28px;

    transition: border-color 0.2s, box-shadow 0.2s;
}


.chat-input-box:focus-within {
    border-color: #10a37f;
    box-shadow: 0 0 0 1px rgba(16, 163, 127, 0.3);
}

/* Left icons */
.chat-left-icons {
    display: flex;
    gap: 4px;
}

.icon-btn {
    font-size: 1.2rem;
    width: 37px;
    height: 37px;
    border-radius: 50%;
    border: none;
    background: transparent;
    color: #6b7280;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}

.icon-btn:hover {
    background: #f3f4f6;
}

/* Input */
.chat-input {
    flex: 1;
    border: none;
    outline: none;
    font-size: 15px;
    padding: 6px;
    background: transparent;
    color: #111827;
}

.chat-input::placeholder {
    color: #9ca3af;
}

/* Send / mic button */
.chat-send-btn {
    width: 38px;
    height: 38px;

    border-radius: 50%;
    border: none;

    background: #f3f4f6;     /* light gray */
    color: #9ca3af;          /* dim icon */

    display: flex;
    align-items: center;
    justify-content: center;

    opacity: 0.5;            /* dimmed */
    cursor: not-allowed;

    transition: opacity 0.2s, background 0.2s, color 0.2s;
}

.chat-send-btn.loading {
    opacity: 1;
    pointer-events: auto;
}

.chat-send-btn.active {
    opacity: 1;
    cursor: pointer;
    background: #000;
    color: #fff;
}


.chat-send-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

</style>