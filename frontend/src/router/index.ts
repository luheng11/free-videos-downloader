import { createRouter, createWebHistory } from "vue-router";

const routes = [
  {
    path: "/",
    name: "home",
    component: () => import("../views/Home.vue"),
    meta: { title: "万能视频下载" },
  },
  {
    path: "/batch",
    name: "batch",
    component: () => import("../views/Batch.vue"),
    meta: { title: "批量下载" },
  },
  {
    path: "/tools",
    name: "tools",
    component: () => import("../views/Tools.vue"),
    meta: { title: "AI 工具" },
  },
  {
    path: "/vip",
    name: "vip",
    component: () => import("../views/Vip.vue"),
    meta: { title: "会员中心" },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

router.afterEach((to) => {
  document.title = `${to.meta.title || "万能视频下载"} | VidPull`;
});

export default router;
