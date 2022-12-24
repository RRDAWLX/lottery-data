<template>
  <div class="navi">
    <router-link class="router-link" :to="{ name: 'union-lotto' }">双色球</router-link>
    <router-link class="router-link" :to="{ name: 'super-lotto' }">超级大乐透</router-link>
  </div>
  <router-view v-slot="{ Component }">
    <template v-if="Component">
      <suspense>
        <component :is="Component" />
      </suspense>
    </template>
  </router-view>
</template>

<style>
#app {
  flex: auto;
}
</style>

<style scoped>
.navi {
  display: flex;
  justify-content: space-evenly;
}

.router-link {
  padding-left: 5px;
  padding-right: 5px;
}

.router-link-active {
  color: #fff;
  background-color: #646cff;
}
</style>
