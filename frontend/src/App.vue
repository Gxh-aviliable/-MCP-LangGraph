<script setup lang="ts">
import ChatInterface from './components/ChatInterface.vue'
</script>

<template>
  <div class="app-container">
    <header class="app-header">
      <h1>🌍 旅行规划助手</h1>
      <p>告诉我您的旅行想法，我来为您规划完美行程</p>
    </header>
    <main class="app-main">
      <ChatInterface />
    </main>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  background: #f5f7fa;
  min-height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-height: 100vh;
}

.app-header {
  text-align: center;
  padding: 20px;
  background: white;
  border-bottom: 1px solid #eee;
  flex-shrink: 0;
}

.app-header h1 {
  color: #2c3e50;
  font-size: 24px;
  margin-bottom: 4px;
}

.app-header p {
  color: #7f8c8d;
  font-size: 14px;
}

.app-main {
  flex: 1;
  overflow: hidden;
  background: white;
}
</style>