'use client';
import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Bot, User } from 'lucide-react'

function renderMarkdown(text, isUser) {
  if (!text) return null
  const lines = text.split('\n')
  return lines.map((line, li) => {
    const parts = []
    const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g
    let lastIdx = 0
    let match
    while ((match = regex.exec(line)) !== null) {
      if (match.index > lastIdx) {
        parts.push(line.slice(lastIdx, match.index))
      }
      if (match[2]) {
        parts.push(<strong key={match.index} className={`font-bold ${isUser ? 'text-white' : 'text-slate-900'}`}>{match[2]}</strong>)
      } else if (match[3]) {
        parts.push(<em key={match.index} className="italic">{match[3]}</em>)
      } else if (match[4]) {
        parts.push(
          <code key={match.index} className={`px-1.5 py-0.5 rounded text-xs font-mono border ${isUser ? 'bg-blue-700 border-blue-500 text-blue-50' : 'bg-slate-100 border-slate-200 text-blue-700'}`}>
            {match[4]}
          </code>
        )
      }
      lastIdx = match.index + match[0].length
    }
    if (lastIdx < line.length) parts.push(line.slice(lastIdx))
    return (
      <span key={li}>
        {parts}
        {li < lines.length - 1 && <br />}
      </span>
    )
  })
}

export default function ChatInterface({ messages = [], onSend, isLoading, placeholder }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || isLoading) return
    onSend(trimmed)
    setInput('')
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-4 px-2 py-3 min-h-0">
        <AnimatePresence initial={false}>
          {messages.map((msg, i) => {
            const isUser = msg.role === 'user';
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm border ${isUser ? 'bg-blue-100 border-blue-200 text-blue-700' : 'bg-slate-100 border-slate-200 text-slate-600'}`}>
                  {isUser ? <User size={15} /> : <Bot size={15} />}
                </div>
                <div className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm border ${isUser ? 'bg-blue-600 text-white rounded-tr-sm border-blue-700' : 'bg-white text-slate-700 rounded-tl-sm border-slate-200'}`}>
                  {msg.role === 'assistant' ? renderMarkdown(msg.content, isUser) : msg.content}
                </div>
              </motion.div>
            )
          })}
        </AnimatePresence>

        {isLoading && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center shadow-sm">
              <Bot size={15} className="text-slate-600" />
            </div>
            <div className="px-5 py-4 bg-white border border-slate-200 rounded-2xl rounded-tl-sm shadow-sm">
              <div className="flex gap-1.5">
                <span className="typing-dot w-1.5 h-1.5 rounded-full bg-slate-400" />
                <span className="typing-dot w-1.5 h-1.5 rounded-full bg-slate-400" />
                <span className="typing-dot w-1.5 h-1.5 rounded-full bg-slate-400" />
              </div>
            </div>
          </motion.div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="pt-3 border-t border-slate-200 mt-2">
        <div className="flex gap-2">
          <textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder={placeholder || 'Type your message…'}
            className="input-field resize-none text-sm flex-1 py-2.5 bg-slate-50"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="btn-primary self-end px-4 py-3 shadow-md"
          >
            <Send size={16} />
          </button>
        </div>
        <p className="text-xs text-slate-500 mt-2 text-right">Press Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  )
}
