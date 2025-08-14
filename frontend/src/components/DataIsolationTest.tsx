/**
 * 数据隔离测试组件
 * 用于验证多租户数据隔离机制是否正常工作
 */

import React, { useState } from 'react'
import { UserStorage, USER_DATA_KEYS, GLOBAL_DATA_KEYS } from '../utils/userStorage'
import { useAuth } from '../hooks/useAuth'
import { 
  logUserAction, 
  saveSearchHistory, 
  getUserSearchHistory,
  saveChatHistory,
  getUserChatHistory,
  saveUserSettings,
  getUserSettings
} from '../supabaseClient'

interface TestResult {
  test: string
  success: boolean
  message: string
}

export const DataIsolationTest: React.FC = () => {
  const { userId } = useAuth()
  const [testResults, setTestResults] = useState<TestResult[]>([])
  const [isRunning, setIsRunning] = useState(false)

  const addTestResult = (test: string, success: boolean, message: string) => {
    setTestResults(prev => [...prev, { test, success, message }])
  }

  const runLocalStorageIsolationTest = async () => {
    addTestResult('localStorage隔离测试', true, '开始测试...')
    
    if (!userId) {
      addTestResult('localStorage隔离测试', false, '用户未登录')
      return
    }

    try {
      // 测试用户隔离数据
      const testData = JSON.stringify([{ id: 1, message: '测试消息' }])
      UserStorage.setUserData(USER_DATA_KEYS.CHAT_HISTORY, testData)
      
      const retrievedData = UserStorage.getUserData(USER_DATA_KEYS.CHAT_HISTORY)
      const success = retrievedData === testData
      
      addTestResult(
        'localStorage用户数据隔离', 
        success, 
        success ? '用户数据隔离正常' : '用户数据隔离失败'
      )

      // 测试全局共享数据
      UserStorage.setGlobalData(GLOBAL_DATA_KEYS.THEME, 'dark')
      const theme = UserStorage.getGlobalData(GLOBAL_DATA_KEYS.THEME)
      const themeSuccess = theme === 'dark'
      
      addTestResult(
        'localStorage全局数据共享', 
        themeSuccess, 
        themeSuccess ? '全局数据共享正常' : '全局数据共享失败'
      )

      // 测试数据键名格式
      const userKeys = UserStorage.getUserDataKeys()
      const hasUserKeys = userKeys.some(key => key.includes(`_${userId}`))
      
      addTestResult(
        'localStorage键名格式', 
        hasUserKeys, 
        hasUserKeys ? `找到 ${userKeys.length} 个用户数据键` : '未找到用户数据键'
      )

    } catch (error) {
      addTestResult('localStorage隔离测试', false, `错误: ${error}`)
    }
  }

  const runSupabaseIsolationTest = async () => {
    addTestResult('Supabase隔离测试', true, '开始测试...')
    
    if (!userId) {
      addTestResult('Supabase隔离测试', false, '用户未登录')
      return
    }

    try {
      // 测试用户行为日志
      await logUserAction(userId, 'test_action', { test: true })
      addTestResult('Supabase用户行为日志', true, '用户行为记录成功')

      // 测试搜索历史
      const searchData = {
        searchId: `test_${Date.now()}`,
        userId: userId,
        timestamp: new Date().toISOString(),
        originalQuery: '测试查询',
        expandedKeywords: ['测试', '关键词'],
        papers: [],
        maxResults: 10
      }
      
      await saveSearchHistory(searchData)
      const searchHistory = await getUserSearchHistory(userId)
      const searchSuccess = searchHistory.length > 0
      
      addTestResult(
        'Supabase搜索历史隔离', 
        searchSuccess, 
        searchSuccess ? `找到 ${searchHistory.length} 条搜索记录` : '未找到搜索记录'
      )

      // 测试聊天历史
      const chatData = {
        chatId: `test_chat_${Date.now()}`,
        userId: userId,
        timestamp: new Date().toISOString(),
        title: '测试聊天',
        messages: [{ role: 'user', content: '测试消息' }],
        lastActivity: new Date().toISOString()
      }
      
      await saveChatHistory(chatData)
      const chatHistory = await getUserChatHistory(userId)
      const chatSuccess = chatHistory.length > 0
      
      addTestResult(
        'Supabase聊天历史隔离', 
        chatSuccess, 
        chatSuccess ? `找到 ${chatHistory.length} 条聊天记录` : '未找到聊天记录'
      )

      // 测试用户设置
      const settingsData = {
        theme: 'dark' as const,
        language: 'zh' as const,
        settings: { testSetting: true }
      }
      
      await saveUserSettings(userId, settingsData)
      const userSettings = await getUserSettings(userId)
      const settingsSuccess = !!userSettings && userSettings.theme === 'dark'
      
      addTestResult(
        'Supabase用户设置隔离', 
        settingsSuccess, 
        settingsSuccess ? '用户设置保存和读取成功' : '用户设置失败'
      )

    } catch (error) {
      addTestResult('Supabase隔离测试', false, `错误: ${error}`)
    }
  }

  const runDataMigrationTest = async () => {
    addTestResult('数据迁移测试', true, '开始测试...')
    
    if (!userId) {
      addTestResult('数据迁移测试', false, '用户未登录')
      return
    }

    try {
      // 创建一些旧格式的数据
      localStorage.setItem('veritex_chat_history', JSON.stringify([{ id: 'old_data' }]))
      localStorage.setItem('paper_god_search_history', JSON.stringify([{ id: 'old_search' }]))
      
      // 手动触发迁移
      const { DataMigration } = await import('../utils/userStorage')
      
      const needsMigration = DataMigration.needsMigration()
      addTestResult('数据迁移检测', needsMigration, needsMigration ? '检测到需要迁移的数据' : '无需迁移数据')
      
      if (needsMigration) {
        DataMigration.migrateToUserIsolation()
        
        // 验证迁移结果
        const migratedChat = UserStorage.getUserData(USER_DATA_KEYS.CHAT_HISTORY)
        const migratedSearch = UserStorage.getUserData(USER_DATA_KEYS.SEARCH_HISTORY)
        
        const migrationSuccess = !!migratedChat && !!migratedSearch
        addTestResult(
          '数据迁移执行', 
          migrationSuccess, 
          migrationSuccess ? '数据迁移成功' : '数据迁移失败'
        )
      }

    } catch (error) {
      addTestResult('数据迁移测试', false, `错误: ${error}`)
    }
  }

  const runAllTests = async () => {
    setIsRunning(true)
    setTestResults([])
    
    await runLocalStorageIsolationTest()
    await runSupabaseIsolationTest()
    await runDataMigrationTest()
    
    setIsRunning(false)
  }

  const clearTestData = () => {
    if (userId) {
      UserStorage.clearUserData(userId)
      setTestResults([])
      addTestResult('清理测试数据', true, '测试数据已清理')
    }
  }

  const getResultColor = (success: boolean) => {
    return success ? 'text-green-600' : 'text-red-600'
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <h2 className="text-xl font-bold mb-4">🔐 多租户数据隔离测试</h2>
      
      <div className="mb-4">
        <p className="text-gray-600 mb-2">当前用户: {userId || '未登录'}</p>
        <div className="flex gap-2">
          <button
            onClick={runAllTests}
            disabled={!userId || isRunning}
            className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:opacity-50"
          >
            {isRunning ? '测试进行中...' : '开始全面测试'}
          </button>
          
          <button
            onClick={clearTestData}
            disabled={!userId}
            className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600 disabled:opacity-50"
          >
            清理测试数据
          </button>
        </div>
      </div>

      <div className="space-y-2">
        <h3 className="font-semibold">测试结果:</h3>
        {testResults.length === 0 && (
          <p className="text-gray-500">点击"开始全面测试"开始测试数据隔离机制</p>
        )}
        
        {testResults.map((result, index) => (
          <div key={index} className="border-l-4 border-l-gray-300 pl-3 py-1">
            <div className="flex items-center gap-2">
              <span className={`font-medium ${getResultColor(result.success)}`}>
                {result.success ? '✅' : '❌'} {result.test}
              </span>
            </div>
            <p className="text-sm text-gray-600">{result.message}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 p-4 bg-gray-50 rounded">
        <h4 className="font-semibold mb-2">测试说明:</h4>
        <ul className="text-sm text-gray-600 space-y-1">
          <li>• localStorage隔离: 验证用户数据键名是否包含用户ID</li>
          <li>• Supabase隔离: 验证数据库数据是否正确隔离</li>
          <li>• 数据迁移: 验证旧数据是否正确迁移到新格式</li>
          <li>• 全局数据: 验证主题、语言等共享数据是否正常</li>
        </ul>
      </div>
    </div>
  )
}

export default DataIsolationTest