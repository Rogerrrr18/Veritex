import React from 'react';
import { calculateTokenUsage, getTokenColor, MAX_TOKENS } from '../utils/tokenCounter';

interface TokenProgressProps {
  messages: any[];
  size?: number;
  showText?: boolean;
}

const TokenProgress: React.FC<TokenProgressProps> = ({ 
  messages, 
  size = 36, 
  showText = true 
}) => {
  const { totalTokens, percentage, isNearLimit, isOverLimit } = calculateTokenUsage(messages);
  const color = getTokenColor(percentage);
  
  const radius = (size - 4) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDasharray = circumference;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;
  
  return (
    <div 
      style={{ 
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        gap: 8
      }}
      title={`Token使用情况: ${totalTokens}/${MAX_TOKENS} (${percentage.toFixed(1)}%)`}
    >
      {/* SVG圆环 */}
      <div style={{ position: 'relative' }}>
        <svg
          width={size}
          height={size}
          style={{ 
            transform: 'rotate(-90deg)',
            filter: isOverLimit ? 'drop-shadow(0 0 4px rgba(239,68,68,0.5))' : undefined
          }}
        >
          {/* 背景圆环 */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="rgba(255,255,255,0.1)"
            strokeWidth={3}
            fill="transparent"
          />
          {/* 进度圆环 */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeWidth={3}
            fill="transparent"
            strokeDasharray={strokeDasharray}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{
              transition: 'stroke-dashoffset 0.3s ease, stroke 0.3s ease',
              opacity: percentage > 0 ? 1 : 0.3
            }}
          />
        </svg>
        
        {/* 中心显示百分比 */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            fontSize: size > 32 ? '10px' : '8px',
            fontWeight: '600',
            color: color,
            fontFamily: 'monospace'
          }}
        >
          {Math.round(percentage)}%
        </div>
      </div>
      
      {/* 可选的文本显示 */}
      {showText && (
        <div
          style={{
            fontSize: '11px',
            color: isOverLimit ? '#ef4444' : isNearLimit ? '#f59e0b' : '#a1a1aa',
            fontFamily: 'monospace'
          }}
        >
          <div style={{ fontWeight: '600' }}>
            {totalTokens.toLocaleString()}/{MAX_TOKENS.toLocaleString()}
          </div>
          <div style={{ fontSize: '9px', opacity: 0.8 }}>
            tokens
          </div>
        </div>
      )}
      
      {/* 警告图标 */}
      {isOverLimit && (
        <div
          style={{
            color: '#ef4444',
            fontSize: '14px',
            animation: 'pulse 1.5s infinite'
          }}
          title="Token超出限制！请考虑开始新对话。"
        >
          ⚠️
        </div>
      )}
      
      <style>
        {`
          @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
          }
        `}
      </style>
    </div>
  );
};

export default TokenProgress;