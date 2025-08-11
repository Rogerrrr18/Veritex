// Token计算工具
// 这是一个简化的token计算，实际token数可能会有差异

const AVERAGE_TOKEN_PER_CHAR = 0.75; // 中英混合文本的平均token/字符比例
const MAX_TOKENS = 4000; // 4k token限制

export function estimateTokens(text: string): number {
  if (!text) return 0;
  
  // 简化的token估算：
  // - 英文单词平均1.3个token
  // - 中文字符平均1个token  
  // - 标点符号0.5个token
  
  const chineseChars = (text.match(/[\u4e00-\u9fff]/g) || []).length;
  const englishWords = (text.match(/[a-zA-Z]+/g) || []).length;
  const punctuation = (text.match(/[.,!?;:"'()[\]{}\-]/g) || []).length;
  const whitespace = (text.match(/\s/g) || []).length;
  
  const estimatedTokens = 
    chineseChars * 1.0 +           // 中文字符
    englishWords * 1.3 +           // 英文单词
    punctuation * 0.5 +            // 标点符号
    whitespace * 0.1;              // 空格
  
  return Math.ceil(estimatedTokens);
}

export function calculateTokenUsage(messages: any[]): {
  totalTokens: number;
  percentage: number;
  isNearLimit: boolean;
  isOverLimit: boolean;
} {
  const totalTokens = messages.reduce((total, message) => {
    return total + estimateTokens(message.text || '');
  }, 0);
  
  const percentage = Math.min((totalTokens / MAX_TOKENS) * 100, 100);
  
  return {
    totalTokens,
    percentage,
    isNearLimit: percentage > 80,
    isOverLimit: percentage > 100
  };
}

export function getTokenColor(percentage: number): string {
  if (percentage > 95) return '#ef4444'; // 红色 - 超限
  if (percentage > 80) return '#f59e0b'; // 橙色 - 接近限制
  if (percentage > 60) return '#eab308'; // 黄色 - 使用较多
  return '#10b981'; // 绿色 - 正常使用
}

export { MAX_TOKENS };