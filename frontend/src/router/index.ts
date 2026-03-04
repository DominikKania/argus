import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/components/layout/MainLayout.vue'

const routes = [
  {
    path: '/',
    component: MainLayout,
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: 'Dashboard' },
      },
      {
        path: 'ampel',
        name: 'ampel',
        component: () => import('@/views/AmpelView.vue'),
        meta: { title: 'Ampel' },
      },
      {
        path: 'thesen',
        name: 'thesen',
        component: () => import('@/views/ThesenView.vue'),
        meta: { title: 'Thesen' },
      },
      {
        path: 'kurse',
        name: 'kurse',
        component: () => import('@/views/KurseView.vue'),
        meta: { title: 'Kurse' },
      },
      {
        path: 'research',
        name: 'research',
        component: () => import('@/views/ResearchView.vue'),
        meta: { title: 'Research' },
      },
      {
        path: 'news',
        name: 'news',
        component: () => import('@/views/NewsView.vue'),
        meta: { title: 'News' },
      },
      {
        path: 'prompt-kontext',
        name: 'prompt-kontext',
        component: () => import('@/views/PromptKontextView.vue'),
        meta: { title: 'Prompt-Kontext' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
