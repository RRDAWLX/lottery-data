import { createRouter, createWebHistory } from 'vue-router';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      name: 'union-lotto',
      path: '/union-lotto',
      component: () => import('./pages/union-lotto.vue'),
    },
    {
      name: 'super-lotto',
      path: '/super-lotto',
      component: () => import('./pages/super-lotto.vue'),
    },
    {
      name: 'default',
      path: '/:path(.*)',
      redirect: 'union-lotto',
    },
  ],
});

export default router;