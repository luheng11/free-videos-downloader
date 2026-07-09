<script setup lang="ts">
import { RouterView } from "vue-router";
import NavBar from "./components/NavBar.vue";
import FooterBar from "./components/FooterBar.vue";
</script>

<template>
  <div class="min-h-screen flex flex-col bg-gradient-to-b from-brand-light/30 via-white to-white">
    <NavBar />
    <main class="flex-1">
      <RouterView />
    </main>
    <FooterBar />
  </div>
</template>
