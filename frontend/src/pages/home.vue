<template>
  <div class="home">
    <div>home</div>
    <el-button type="primary">Primary</el-button>
  </div>
</template>

<script>
export default {
  name: 'home',

  async created () {
    let res = await fetch('/api/getLotteryData/unionLotto');
    console.log(await res.json());
  },
}
</script>
