<template>
    <div class="chat-input-container" :style="boxStyle">
    <form method="POST" @submit.prevent="handleSubmit" v-if="canComment" class="chat-form">
        
        <!-- Reply Banner -->
        <div v-if="replyingTo" class="reply-banner">
            <div class="reply-info">
                <span class="reply-label">Replying to</span>
                <span class="reply-name">{{ replyingTo.owner.name }}</span>
            </div>
            <button type="button" class="close-reply-btn" @click="$emit('cancel-reply')">
                <i class="fas fa-times"></i>
            </button>
        </div>

        <div class="chat-input-box" :class="{'has-reply': replyingTo}">
            
            <!-- Mentions Popup -->
            <div v-if="showMentions && filteredUsers.length" class="mentions-popup">
                <div 
                    v-for="(user, index) in filteredUsers" 
                    :key="user.id" 
                    class="mention-item"
                    :class="{ active: index === highlightedIndex }"
                    @click="selectUser(user)"
                >
                    <img :src="user.profile_picture" class="avatar-small">
                    <span>{{ user.name }}</span>
                </div>
            </div>

            <!-- Emoji Popup -->
            <div v-if="showEmojiPicker" class="emoji-popup">
                <div v-if="loadingEmojis" class="text-center p-2">Loading emojis...</div>
                <div v-else class="emoji-grid">
                    <span 
                        v-for="(emoji, index) in emojis" 
                        :key="index" 
                        class="emoji-item"
                        @click="insertEmoji(emoji)"
                        :title="emoji.annotation"
                    >{{ emoji.emoji }}</span>
                </div>
            </div>

            <!-- Left Icons -->
            <div class="chat-left-icons">
                <!-- <button type="button" class="icon-btn">
                    <i class="fa-solid fa-circle-plus"></i>
                </button> -->
                <button type="button" class="icon-btn" id="emoji-btn" @click="toggleEmojiPicker">
                    <i class="fa-regular fa-face-smile"></i>
                </button>
                 <button type="button" class="icon-btn" id="mention-btn" @click="insertMention">
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
                @input="handleInput"
                @keydown="handleKeydown"
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

    <div v-else class="show-login-user">
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
            },
            users: {
                type: Array,
                default: () => []
            },
            replyingTo: {
                type: Object,
                default: null
            }
        },
        data() {
            return {
                content: "",
                auth: window.Auth,
                errors: new Errors(),
                isSending: false,
                showMentions: false,
                mentionSearch: "",
                highlightedIndex: 0,
                mentionStartPos: -1,
                showEmojiPicker: false,
                emojis: [],
                loadingEmojis: false,
                boxStyle: {}
            }
        },
        mounted() {
            this.updatePosition();
            window.addEventListener('resize', this.updatePosition);
            // Also update on scroll of parent/window just in case, though fixed shouldn't need it unless layout shifts
            window.addEventListener('scroll', this.updatePosition, true); 
        },
        destroyed() {
            window.removeEventListener('resize', this.updatePosition);
            window.removeEventListener('scroll', this.updatePosition, true);
        },
        methods: {
            updatePosition() {
                const feed = this.$el.closest('.discussion-feed');
                if (feed) {
                    const rect = feed.getBoundingClientRect();
                    this.boxStyle = {
                        width: `${rect.width}px`,
                        left: `${rect.left}px`,
                        position: 'fixed',
                        bottom: '0',
                        zIndex: '1000'
                    };
                }
            },
            toggleEmojiPicker() {
                this.showEmojiPicker = !this.showEmojiPicker;
                if (this.showEmojiPicker && this.emojis.length === 0) {
                    this.fetchEmojis();
                }
                console.log("all emoji's : ",this.emojis)
            },
            fetchEmojis() {
                this.loadingEmojis = true;
                // Using axios locally if available or fetch
                fetch('/forum/threads/api/emojis')
                    .then(response => response.json())
                    .then(data => {
                        this.emojis = data;
                    })
                    .catch(err => {
                        console.error("Failed to load emojis", err);
                    })
                    .finally(() => {
                        this.loadingEmojis = false;
                    });
            },
            insertEmoji(emoji) {
                const input = this.$refs.input;
                const cursor = input.selectionStart || this.content.length;
                const text = this.content;
                const before = text.slice(0, cursor);
                const after = text.slice(cursor);
                
                this.content = before + emoji.emoji + after;
                
                this.$nextTick(() => {
                    input.focus();
                    const newCursorPos = cursor + emoji.emoji.length;
                    input.setSelectionRange(newCursorPos, newCursorPos);
                });
            },
            handleSubmit() {
                if (!this.content.trim()) return;
                this.isSending = true;

                const payload = { content: this.content };
                if (this.replyingTo) {
                    payload.parent_id = this.replyingTo.id;
                }

                axios.post(`/forum/api/threads/${this.threadId}/comments`, payload)
                    .then(({data}) => {
                        this.content = "";
                        this.showEmojiPicker = false;
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
            },
            handleInput(e) {
                const cursor = e.target.selectionStart;
                const text = this.content;
                const textBeforeCursor = text.slice(0, cursor);
                const atIndex = textBeforeCursor.lastIndexOf('@');

                if (atIndex !== -1 && (atIndex === 0 || textBeforeCursor[atIndex - 1] === ' ')) {
                    this.mentionSearch = textBeforeCursor.slice(atIndex + 1);
                    // Check if search contains invalid characters (like newline) if needed
                    this.mentionStartPos = atIndex;
                    this.showMentions = true;
                    this.highlightedIndex = 0;
                    this.showEmojiPicker = false; // Close emoji picker if mention starts
                } else {
                    this.showMentions = false;
                }
            },
            handleKeydown(e) {
                this.clearInput('content');
                if (this.showMentions && this.filteredUsers.length) {
                    if (e.key === 'ArrowUp') {
                        e.preventDefault();
                        this.highlightedIndex = (this.highlightedIndex - 1 + this.filteredUsers.length) % this.filteredUsers.length;
                    } else if (e.key === 'ArrowDown') {
                        e.preventDefault();
                        this.highlightedIndex = (this.highlightedIndex + 1) % this.filteredUsers.length;
                    } else if (e.key === 'Enter' || e.key === 'Tab') {
                        e.preventDefault();
                        this.selectUser(this.filteredUsers[this.highlightedIndex]);
                    } else if (e.key === 'Escape') {
                        this.showMentions = false;
                    }
                } else if (e.key === 'Escape') {
                    this.showEmojiPicker = false;
                }
            },
            selectUser(user) {
                const before = this.content.slice(0, this.mentionStartPos);
                const after = this.content.slice(this.$refs.input.selectionStart);
                this.content = `${before}@${user.name} ${after}`;
                this.showMentions = false;
                this.$nextTick(() => {
                    this.$refs.input.focus();
                });
            },
            insertMention() {
                const input = this.$refs.input;
                const cursor = input.selectionStart || this.content.length;
                const text = this.content;
                const before = text.slice(0, cursor);
                const after = text.slice(cursor);
                
                // Add space before @ if needed
                let insertion = '@';
                if (cursor > 0 && text[cursor - 1] !== ' ' && text[cursor - 1] !== '\n') {
                    insertion = ' @';
                }

                this.content = before + insertion + after;
                
                this.$nextTick(() => {
                    input.focus();
                    const newCursorPos = cursor + insertion.length;
                    input.setSelectionRange(newCursorPos, newCursorPos);
                    
                    // Trigger mention logic
                    this.handleInput({ target: input });
                });
            }
        },
        computed: {
            canComment() {
                return  !! window.Auth && window.Auth.email_verified;
            },
            filteredUsers() {
                if (!this.mentionSearch) return this.users;
                const search = this.mentionSearch.toLowerCase();
                return this.users.filter(u => u.name.toLowerCase().includes(search));
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
    .chat-input-container {
        background: #fff;
        padding: 12px;
        border-top: 1px solid #e5e7eb;
    }

    .input-group:focus-within {
        border-color: #aaa !important;
    }
    .form-control::placeholder {
        color: #999;
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

.chat-input-box {
    position: relative; /* For mentions popup */
}

.mentions-popup {
    position: absolute;
    bottom: 100%;
    left: 0;
    width: 300px;
    max-height: 250px;
    overflow-y: auto;
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 8px;
    box-shadow: 0 -4px 12px rgba(0,0,0,0.1);
    z-index: 9999;
    margin-bottom: 8px;
    display: flex;
    flex-direction: column;
}

.mention-item {
    display: flex;
    align-items: center;
    padding: 10px 14px;
    cursor: pointer;
    border-bottom: 1px solid #f0f0f0;
    transition: background 0.1s;
}

.mention-item:last-child {
    border-bottom: none;
}

.mention-item.active, .mention-item:hover {
    background: #f3f4f6;
}

.avatar-small {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    margin-right: 12px;
    object-fit: cover;
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

.emoji-popup {
    position: absolute;
    bottom: 100%;
    left: 0;
    width: 320px;
    height: 250px;
    overflow-y: auto;
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 8px;
    box-shadow: 0 -4px 12px rgba(0,0,0,0.1);
    z-index: 9999;
    margin-bottom: 8px;
    display: flex;
    flex-direction: column;
}

.emoji-grid {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 5px;
    padding: 10px;
}

.emoji-item {
    font-size: 1.5rem;
    cursor: pointer;
    text-align: center;
    border-radius: 4px;
    transition: background 0.1s;
    user-select: none;
}

.emoji-item:hover {
    background: #f3f4f6;
}

.show-login-user{
    text-align: center;
    font-size: 0.875rem;
    color: #6c757d;
}

/* Reply Banner Styles */
.reply-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #f0f2f5;
    padding: 8px 16px;
    border-radius: 12px 12px 0 0;
    border: 1px solid #e5e7eb;
    border-bottom: none;
    margin-bottom: -1px; /* Overlap border */
    position: relative;
    z-index: 1;
}

.reply-info {
    display: flex;
    flex-direction: column;
    font-size: 0.85rem;
}

.reply-label {
    color: #65676b;
    font-size: 0.75rem;
}

.reply-name {
    font-weight: 600;
    color: #050505;
}

.close-reply-btn {
    background: none;
    border: none;
    color: #65676b;
    cursor: pointer;
    font-size: 1rem;
    padding: 4px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s;
}

.close-reply-btn:hover {
    background: #e4e6eb;
}

.chat-input-box.has-reply {
    border-top-left-radius: 0;
    border-top-right-radius: 0;
}

@media (max-width: 768px) {
    .chat-input-box{
        width: 100%;
        min-height : 0;
        padding: 8px 12px;

        
    }
    #emoji-btn {
        display: none;
    }
}

</style>