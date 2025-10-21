import React from 'react';
import { useGlobal } from '../contexts/GlobalContext';

interface ThemeLanguageSwitcherProps {
  className?: string;
  compact?: boolean; // 紧凑模式，用于移动端
}

const ThemeLanguageSwitcher: React.FC<ThemeLanguageSwitcherProps> = ({ 
  className = '', 
  compact = false 
}) => {
  const { theme, toggleTheme, language, toggleLanguage, t } = useGlobal();

  const switcherStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: compact ? 8 : 12,
    padding: compact ? '4px' : '8px',
    borderRadius: 8,
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.1)'
  };

  const buttonBaseStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: compact ? 32 : 36,
    height: compact ? 32 : 36,
    borderRadius: 6,
    border: 'none',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    fontSize: compact ? 14 : 16,
    background: 'transparent',
    color: theme === 'dark' ? '#fff' : '#333'
  };

  const activeButtonStyle: React.CSSProperties = {
    ...buttonBaseStyle,
    background: theme === 'dark' ? 'rgba(59,176,230,0.2)' : 'rgba(59,176,230,0.1)',
    border: '1px solid rgba(59,176,230,0.3)'
  };

  return (
    <div className={`theme-language-switcher ${className}`} style={switcherStyle}>
      {/* 主题切换 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <button
          onClick={toggleTheme}
          style={buttonBaseStyle}
          title={theme === 'dark' ? t('theme.light') : t('theme.dark')}
          aria-label={t('theme.switch')}
        >
          {theme === 'dark' ? (
            // 太阳图标 (白天模式)
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="10" cy="10" r="4" fill="currentColor" />
              <g stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <line x1="10" y1="2" x2="10" y2="4"/>
                <line x1="10" y1="16" x2="10" y2="18"/>
                <line x1="2" y1="10" x2="4" y2="10"/>
                <line x1="16" y1="10" x2="18" y2="10"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                <line x1="14.36" y1="14.36" x2="15.78" y2="15.78"/>
                <line x1="4.22" y1="15.78" x2="5.64" y2="14.36"/>
                <line x1="14.36" y1="5.64" x2="15.78" y2="4.22"/>
              </g>
            </svg>
          ) : (
            // 月亮图标 (夜间模式)
            <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12.5 2.5C12.5 6.64 9.14 10 5 10C6.19 13.08 9.06 15.25 12.5 15.25C16.64 15.25 20 11.89 20 7.75C20 4.84 18.39 2.34 15.9 1.05C14.65 1.52 13.53 2.93 12.5 2.5Z" fill="currentColor"/>
            </svg>
          )}
        </button>
      </div>

      {/* 分隔线 */}
      <div style={{
        width: 1,
        height: compact ? 20 : 24,
        background: 'rgba(255,255,255,0.1)'
      }} />

      {/* 语言切换 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <button
          onClick={toggleLanguage}
          style={language === 'zh' ? activeButtonStyle : buttonBaseStyle}
          title="中文"
          aria-label={t('language.switch')}
        >
          <span style={{ fontSize: compact ? 11 : 12, fontWeight: 600 }}>中</span>
        </button>
        <button
          onClick={toggleLanguage}
          style={language === 'en' ? activeButtonStyle : buttonBaseStyle}
          title="English"
          aria-label={t('language.switch')}
        >
          <span style={{ fontSize: compact ? 11 : 12, fontWeight: 600 }}>EN</span>
        </button>
      </div>
    </div>
  );
};

export default ThemeLanguageSwitcher;