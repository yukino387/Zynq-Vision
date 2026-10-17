<template>
  <div class="page-heading">
    <div>
      <h1>未找到</h1>
      <p>这个地址没有对应的页面。</p>
    </div>
  </div>
  <div class="panel">
    <div class="empty">
      <p>
        请从左侧导航进入，或<RouterLink :to="{ name: 'workbench' }"
          >返回检测工作台</RouterLink
        >。
      </p>
    </div>
  </div>
</template>
