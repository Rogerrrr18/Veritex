import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

export type Theme = 'light' | 'dark';
export type Language = 'zh' | 'en';

interface GlobalContextType {
  // 主题相关
  theme: Theme;
  toggleTheme: () => void;
  
  // 语言相关
  language: Language;
  toggleLanguage: () => void;
  t: (key: string) => string;
}

const GlobalContext = createContext<GlobalContextType | undefined>(undefined);

// 翻译字典
const translations = {
  zh: {
    // 首页翻译
    'home.title': 'Smart Academic Literature Search & Management Platform',
    'home.desc': 'Veritex 依托大模型与智能算法，支持关键词扩展、批量论文检索、摘要智能提取与报告导出，帮你快速定位当前的研究进展。',
    'home.placeholder.loggedIn': '请输入关键词或学术问题...',
    'home.placeholder.notLoggedIn': '请先获取内测邀请码',
    'home.button.searchChat': '🔍 Search & Chat',
    'home.button.getBetaCode': 'Get Beta Code',
    'home.button.startTrial': 'Start free trial',
    'home.button.my': 'My',
    
    // 通用翻译
    'common.home': '返回首页',
    'common.back': 'Back',
    'common.export': 'Export CSV',
    'common.view': 'View',
    'common.search': 'Search',
    'common.chat': 'Chat',
    'common.loading': '加载中...',
    'common.error': '错误',
    
    // 主题和语言切换
    'theme.switch': '切换主题',
    'theme.light': '切换为白天模式',
    'theme.dark': '切换为夜间模式',
    'language.switch': '切换语言',
    
    // 聊天界面
    'chat.title': '🤖 Veritex AI Assistant',
    'chat.subtitle': '智能学术助手 • 关键词扩展 • 文献搜索',
    'chat.placeholder': '输入您的学术问题或研究主题...',
    'chat.send': '发送',
    'chat.thinking': 'AI正在思考',
    'chat.hint': '💡 提示：按 Enter 发送，Shift+Enter 换行',
    'chat.welcome': '👋 您好！我是Veritex智能助手。您可以：\n\n📚 发送学术查询，我会为您分析并扩展关键词\n🔍 直接搜索文献\n💬 与我对话交流学术问题\n\n请输入您的问题或研究主题吧！',
    'chat.keywordHint': '💡 已为您分析并扩展关键词，请查看右侧关键词云进行搜索',
    
    // 报告页面
    'report.back': '← Back',
    'report.export': 'Export CSV',
    'report.table.title': 'Title',
    'report.table.authors': 'Authors',
    'report.table.year': 'Year',
    'report.table.abstract': 'Abstract',
    'report.table.link': 'Link',
    'report.abstract.more': 'More',
    'report.abstract.less': 'Less',
    
    // 我的页面
    'my.title': '我的搜索历史',
    'my.totalRecords': '共 {count} 条记录',
    'my.selectedRecords': ' · 已选择 {count} 条',
    'my.selectAll': '全选',
    'my.delete': 'Delete',
    'my.clearAll': 'Clear All',
    'my.noHistory': '还没有搜索历史',
    'my.noHistoryDesc': '开始你的第一次文献搜索吧！',
    'my.startSearch': 'Start Search',
    'my.viewReport': 'View Report',
    'my.reSearch': 'Re-search',
    'my.expandedKeywords': '扩展关键词:',
    'my.papers': '篇文献',
    'my.maxResults': '目标数量:',
    'my.today': '今天',
    'my.yesterday': '昨天',
    'my.daysAgo': '{days}天前',
    
    // 邀请码页面
    'invite.title': '填写内测邀请码',
    'invite.placeholder': '请输入6位内测码',
    'invite.submit': 'Start Beta',
    'invite.verifying': 'Verifying...',
    'invite.error.required': '请输入内测邀请码',
    'invite.error.register': '注册失败',
    'invite.error.network': '注册过程中出错'
  },
  
  en: {
    // 首页翻译
    'home.title': 'Smart Academic Literature Search & Management Platform',
    'home.desc': 'Veritex leverages large language models and intelligent algorithms to support keyword expansion, batch paper retrieval, abstract extraction, and report generation, helping you quickly identify current research progress.',
    'home.placeholder.loggedIn': 'Enter keywords or academic questions...',
    'home.placeholder.notLoggedIn': 'Please get beta invitation code first',
    'home.button.searchChat': '🔍 Search & Chat',
    'home.button.getBetaCode': 'Get Beta Code',
    'home.button.startTrial': 'Start free trial',
    'home.button.my': 'My',
    
    // 通用翻译
    'common.home': 'Home',
    'common.back': 'Back',
    'common.export': 'Export CSV',
    'common.view': 'View',
    'common.search': 'Search',
    'common.chat': 'Chat',
    'common.loading': 'Loading...',
    'common.error': 'Error',
    
    // 主题和语言切换
    'theme.switch': 'Toggle Theme',
    'theme.light': 'Switch to Light Mode',
    'theme.dark': 'Switch to Dark Mode',
    'language.switch': 'Switch Language',
    
    // 聊天界面
    'chat.title': '🤖 Veritex AI Assistant',
    'chat.subtitle': 'Intelligent Academic Assistant • Keyword Expansion • Literature Search',
    'chat.placeholder': 'Enter your academic questions or research topics...',
    'chat.send': 'Send',
    'chat.thinking': 'AI is thinking',
    'chat.hint': '💡 Tip: Press Enter to send, Shift+Enter for new line',
    'chat.welcome': '👋 Hello! I am the Veritex intelligent assistant. You can:\n\n📚 Send academic queries, I will analyze and expand keywords for you\n🔍 Search literature directly\n💬 Chat with me about academic questions\n\nPlease enter your questions or research topics!',
    'chat.keywordHint': '💡 Keywords have been analyzed and expanded for you. Please check the keyword cloud on the right for search',
    
    // 报告页面
    'report.back': '← Back',
    'report.export': 'Export CSV',
    'report.table.title': 'Title',
    'report.table.authors': 'Authors',
    'report.table.year': 'Year',
    'report.table.abstract': 'Abstract',
    'report.table.link': 'Link',
    'report.abstract.more': 'More',
    'report.abstract.less': 'Less',
    
    // 我的页面
    'my.title': 'My Search History',
    'my.totalRecords': 'Total {count} records',
    'my.selectedRecords': ' · Selected {count} items',
    'my.selectAll': 'Select All',
    'my.delete': 'Delete',
    'my.clearAll': 'Clear All',
    'my.noHistory': 'No search history yet',
    'my.noHistoryDesc': 'Start your first literature search!',
    'my.startSearch': 'Start Search',
    'my.viewReport': 'View Report',
    'my.reSearch': 'Re-search',
    'my.expandedKeywords': 'Expanded Keywords:',
    'my.papers': 'papers',
    'my.maxResults': 'Target count:',
    'my.today': 'Today',
    'my.yesterday': 'Yesterday',
    'my.daysAgo': '{days} days ago',
    
    // 邀请码页面
    'invite.title': 'Enter Beta Invitation Code',
    'invite.placeholder': 'Please enter 6-digit beta code',
    'invite.submit': 'Start Beta',
    'invite.verifying': 'Verifying...',
    'invite.error.required': 'Please enter beta invitation code',
    'invite.error.register': 'Registration failed',
    'invite.error.network': 'Error occurred during registration'
  }
};

interface GlobalProviderProps {
  children: ReactNode;
}

export function GlobalProvider({ children }: GlobalProviderProps) {
  // 从localStorage读取保存的主题和语言设置
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('veritex_theme');
    return (saved as Theme) || 'dark';
  });
  
  const [language, setLanguage] = useState<Language>(() => {
    const saved = localStorage.getItem('veritex_language');
    return (saved as Language) || 'zh';
  });

  // 主题切换
  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('veritex_theme', newTheme);
  };

  // 语言切换
  const toggleLanguage = () => {
    const newLanguage = language === 'zh' ? 'en' : 'zh';
    setLanguage(newLanguage);
    localStorage.setItem('veritex_language', newLanguage);
  };

  // 翻译函数
  const t = (key: string): string => {
    const translation = translations[language]?.[key];
    if (!translation) {
      console.warn(`Translation missing for key: ${key} in language: ${language}`);
      return key; // 返回原key作为fallback
    }
    return translation;
  };

  // 应用主题到body
  useEffect(() => {
    document.body.setAttribute('data-theme', theme);
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  const value: GlobalContextType = {
    theme,
    toggleTheme,
    language,
    toggleLanguage,
    t
  };

  return (
    <GlobalContext.Provider value={value}>
      {children}
    </GlobalContext.Provider>
  );
}

export function useGlobal(): GlobalContextType {
  const context = useContext(GlobalContext);
  if (context === undefined) {
    throw new Error('useGlobal must be used within a GlobalProvider');
  }
  return context;
}