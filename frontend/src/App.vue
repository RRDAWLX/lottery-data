<template>
  <router-view />
</template>

<script>
export default {
  name: "App",

  async created() {
    let res = await fetch('/api/getLotteryData/superLotto');
    console.log(await res.json());
  },
};
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 60px;
}
</style>
