import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.montana.junona',
  appName: 'Юнона',
  webDir: 'www',
  server: {
    // Загружаем сайт с удалённого сервера
    url: 'http://72.56.102.240',
    cleartext: true  // Разрешаем HTTP (для разработки)
  },
  ios: {
    contentInset: 'automatic',
    backgroundColor: '#0F0F1A',
    // Разрешаем доступ к контактам
    allowsLinkPreview: false
  },
  plugins: {
    Contacts: {
      // Запрос доступа к контактам
    }
  }
};

export default config;
