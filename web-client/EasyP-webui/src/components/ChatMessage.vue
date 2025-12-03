<template>
  <div class="chat-message-wrapper" :class="wrapperClass">
    <!-- 头像区域 -->
    <div class="avatar-container" v-if="showAvatar">
      <q-avatar size="40px" class="message-avatar shadow-2">
        <q-icon :name="avatarIcon" :color="avatarIconColor" />
      </q-avatar>
    </div>

    <!-- 消息主体 -->
    <div class="chat-message" :class="messageClass">
      <div class="message-meta">
        <span class="message-sender">{{ senderName }}</span>
        <span class="message-time">{{ formatTime(message.timestamp) }}</span>
      </div>

      <div class="message-content">
        <div v-if="message.type === 'final_prompt'" class="final-prompt-container">
          <q-card class="final-prompt-card">
            <q-card-section>
              <div class="text-h6 q-mb-md">
                <q-icon name="auto_awesome" color="primary" />
                最终提示词
              </div>
              <div class="markdown-content" v-html="renderedContent"></div>
            </q-card-section>
            <q-card-actions align="right" v-if="message.isComplete">
              <q-btn
                flat
                icon="content_copy"
                label="复制"
                color="primary"
                @click="copyToClipboard"
              />
              <q-btn
                flat
                icon="download"
                label="下载"
                color="secondary"
                @click="downloadPrompt"
              />
            </q-card-actions>
          </q-card>
        </div>

        <div v-else class="message-text">
          <span v-html="renderedContent"></span>
          <q-spinner-dots
            v-if="!message.isComplete && ['ai', 'final_prompt'].includes(message.type)"
            color="primary"
            size="sm"
            class="q-ml-sm"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { marked } from 'marked';
import { copyToClipboard as copyText, Notify } from 'quasar';
import type { ChatMessage } from 'src/types/websocket';

interface Props {
  message: ChatMessage;
}

const props = defineProps<Props>();

const wrapperClass = computed(() => {
  return {
    'wrapper--user': props.message.type === 'user',
    'wrapper--ai': props.message.type === 'ai' || props.message.type === 'final_prompt',
    'wrapper--system': props.message.type === 'system' || props.message.type === 'error'
  };
});

const showAvatar = computed(() => {
  return ['user', 'ai', 'final_prompt'].includes(props.message.type);
});

const avatarIcon = computed(() => {
  switch (props.message.type) {
    case 'user': return 'person';
    case 'ai': return 'smart_toy';
    case 'final_prompt': return 'auto_awesome';
    default: return 'info';
  }
});

const avatarIconColor = computed(() => {
  switch (props.message.type) {
    case 'user': return 'white'; // 用户头像图标白色
    case 'ai': return 'white';   // AI头像图标白色
    case 'final_prompt': return 'white';
    default: return 'grey';
  }
});

const senderName = computed(() => {
  switch (props.message.type) {
    case 'user': return '你';
    case 'ai': return 'Easy Prompt';
    case 'final_prompt': return 'Easy Prompt';
    case 'system': return '系统消息';
    case 'error': return '错误';
    default: return '未知';
  }
});

const messageClass = computed(() => {
  return {
    'chat-message--system': props.message.type === 'system',
    'chat-message--ai': props.message.type === 'ai',
    'chat-message--user': props.message.type === 'user',
    'chat-message--final-prompt': props.message.type === 'final_prompt',
    'chat-message--error': props.message.type === 'error',
    'chat-message--incomplete': !props.message.isComplete
  };
});


const renderedContent = computed(() => {
  if (props.message.type === 'final_prompt') {
    // 渲染 Markdown
    return marked(props.message.content);
  } else {
    // 简单的文本渲染，保留换行
    return props.message.content.replace(/\n/g, '<br>');
  }
});

const formatTime = (timestamp: Date): string => {
  return timestamp.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

const copyToClipboard = async (): Promise<void> => {
  try {
    await copyText(props.message.content);
    Notify.create({
      type: 'positive',
      message: '已复制到剪贴板',
      position: 'top'
    });
  } catch {
    Notify.create({
      type: 'negative',
      message: '复制失败',
      position: 'top'
    });
  }
};

const downloadPrompt = (): void => {
  const blob = new Blob([props.message.content], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `roleplay-prompt-${Date.now()}.md`;
  a.click();
  URL.revokeObjectURL(url);

  Notify.create({
    type: 'positive',
    message: '提示词已下载',
    position: 'top'
  });
};
</script>

<style scoped lang="scss">
.chat-message-wrapper {
  display: flex;
  margin-bottom: 24px;
  align-items: flex-start;
  width: 100%;

  &.wrapper--user {
    flex-direction: row-reverse;
    
    .avatar-container {
      margin-left: 12px;
      margin-right: 0;
    }

    .chat-message {
      border-top-right-radius: 4px;
    }
  }

  &.wrapper--ai, &.wrapper--system {
    flex-direction: row;

    .avatar-container {
      margin-right: 12px;
      margin-left: 0;
    }

    .chat-message {
      border-top-left-radius: 4px;
    }
  }
}

.avatar-container {
  flex-shrink: 0;
}

.message-avatar {
  background: linear-gradient(135deg, $primary 0%, $accent 100%);
}

.chat-message {
  padding: 16px;
  border-radius: 20px;
  transition: box-shadow 0.2s ease;
  box-shadow: 0 4px 15px rgba(230, 122, 152, 0.15);
  max-width: 80%;
  position: relative;

  &:hover {
    // 移除缩放效果
    box-shadow: 0 6px 20px rgba(230, 122, 152, 0.25);
    z-index: 1;
  }

  &--system {
    background-color: #FFF5F8;
    border-left: 4px solid $secondary;
    width: 100%; // 系统消息通常全宽
    max-width: 100%;
  }

  &--ai {
    background-color: white;
    border: 1px solid #FFE5EC;
  }

  &--user {
    background: linear-gradient(135deg, $primary 0%, $accent 100%);
    color: white;

    .message-meta {
      color: rgba(255, 255, 255, 0.9);
    }

    .message-content {
      color: white;
    }
    
    :deep(code) {
      color: $primary;
      background-color: rgba(255, 255, 255, 0.9);
    }
  }

  &--final-prompt {
    background-color: #F0FFF4;
    border: 1px solid #B7E4C7;
  }

  &--error {
    background-color: #FFF0F0;
    border-left: 4px solid #FF5C8D;
  }

  &--incomplete {
    opacity: 0.9;
  }
}

.message-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  color: $primary;
  opacity: 0.8;
  font-weight: 500;
}

.message-sender {
  font-weight: bold;
  margin-right: 8px;
}

.message-time {
  font-family: monospace;
  font-size: 11px;
}

.message-content {
  line-height: 1.6;
  color: #5D4037;
  font-size: 15px;
}

.message-text {
  word-wrap: break-word;
  white-space: pre-wrap;
}

.final-prompt-container {
  .final-prompt-card {
    box-shadow: none;
    border: 1px solid rgba(152, 221, 202, 0.4);
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.8);
  }
}

.markdown-content {
  :deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5), :deep(h6) {
    margin-top: 1em;
    margin-bottom: 0.5em;
    color: $primary;
  }

  :deep(p) {
    margin-bottom: 1em;
  }

  :deep(strong) {
    font-weight: 600;
    color: $accent;
  }

  :deep(ul), :deep(ol) {
    margin-left: 1.5em;
    margin-bottom: 1em;
  }

  :deep(blockquote) {
    border-left: 4px solid $secondary;
    padding-left: 1em;
    margin: 1em 0;
    font-style: italic;
    color: #888;
    background-color: #FFF5F8;
    padding: 8px 16px;
    border-radius: 0 8px 8px 0;
  }

  :deep(code) {
    background-color: #FFF0F5;
    padding: 2px 4px;
    border-radius: 6px;
    font-family: monospace;
    color: $primary;
  }

  :deep(pre) {
    background-color: #2C1A1D;
    padding: 1em;
    border-radius: 12px;
    overflow-x: auto;
    margin: 1em 0;
    
    code {
      color: #FFC2D1;
      background-color: transparent;
    }
  }
}
</style>
