export const t = {
  // Navigation
  appName: 'GEO CLI',
  appVersion: 'TecAce Software — v2.0',
  interview: '인터뷰',
  pipeline: '파이프라인',
  data: '데이터',
  promptEditor: '프롬프트 편집',
  settings: '설정',
  newAnalysis: '새 분석 시작',

  // Pipeline stages
  stages: {
    brief: '브리프',
    queries: '쿼리',
    testing: '테스트',
    analysis: '분석',
    report: '보고서',
  } as Record<string, string>,

  // Pipeline status
  pipelineStatus: '파이프라인 상태',

  // Interview
  chatPlaceholder: '메시지를 입력하세요...',
  chatWelcome: '아래에 메시지를 입력해서 인터뷰를 시작하세요.',
  chatExample: '예: "삼성전자 갤럭시 브랜드를 분석하고 싶어요."',
  approve: '승인 — 파이프라인 시작',
  restart: '재시작',
  confirmTitle: '수집된 정보 확인',
  queryCount: '생성할 쿼리 수',
  briefComplete: '브리프 완성',
  goToPipeline: '파이프라인으로 이동',

  // Brief fields
  subject: '분석 대상',
  industry: '산업',
  market: '시장',
  website: '웹사이트',
  purpose: '분석 목적',
  competitors: '경쟁사',
  platforms: '플랫폼',
  personas: '페르소나',
  products: '제품',
  keywords: '키워드',
  reportLang: '보고서',
  language: '언어',
  audienceLevel: '독자 수준',

  // Purpose map
  purposeMap: {
    brand_awareness: '브랜드 인지도',
    competitive_analysis: '경쟁사 비교',
    content_strategy: '콘텐츠 전략',
    crisis_monitoring: '위기 모니터링',
  } as Record<string, string>,

  langMap: {
    ko: '한국어',
    en: '영어',
    ja: '일본어',
    zh: '중국어',
  } as Record<string, string>,

  audienceMap: {
    executive: '임원용',
    technical: '기술용',
    marketing: '마케팅용',
  } as Record<string, string>,

  // Pipeline
  runQuery: '쿼리 생성 실행',
  runTesting: 'ChatGPT 테스트 실행',
  runAnalysis: '분석 실행',
  runReport: '보고서 생성',
  rerun: '재실행',
  liveLogs: '실시간 로그',
  clearLogs: '로그 지우기',
  noLogs: '아직 로그가 없습니다.',
  browserWarning: '브라우저 창이 열립니다. ChatGPT 로그인 후 자동으로 쿼리가 실행됩니다.',
  uploadTestResult: '로컬 테스트 결과 업로드',
  downloadReport: '보고서 다운로드',

  // Metrics
  visibility: 'Visibility',
  shareOfVoice: 'Share of Voice',
  avgRank: 'Avg. Rank',
  rank1Count: 'Rank 1 횟수',
  sentimentDist: '감성 분포',
  positive: '긍정',
  negative: '부정',
  neutral: '중립',
  competitorMentions: '경쟁사 언급',
  personaVisibility: '페르소나별 Visibility',

  // Data page
  savedData: '저장된 데이터',
  totalAnalyses: '총 {count}개 분석',
  resumeWork: '이 브리프로 작업 재개',
  artifacts: '산출물',
  noArtifacts: '산출물 파일이 없습니다.',
  preview: '미리보기',
  download: '다운로드',
  noData: '저장된 브리프가 없습니다.',
  deleteBrief: '삭제',

  // Prompts
  editPrompt: '편집할 프롬프트',
  save: '저장',
  saved: '저장 완료',
  resetDefault: '초기화',
  resetDone: '초기값으로 복원됐습니다.',
  unsavedChanges: '미저장 변경',

  // Settings
  apiKey: 'Anthropic API Key',
  model: '모델',
  dataDir: '데이터 디렉토리',
  domSelectors: 'ChatGPT DOM 셀렉터',
  domSelectorsDesc: 'ChatGPT UI가 변경되면 여기서 업데이트하세요.',
  apiKeyNotSet: 'API 키가 설정되지 않았습니다.',

  // Common
  loading: '로딩 중...',
  error: '오류',
  complete: '완료',
  running: '실행 중...',
  pending: '대기',
  cancel: '취소',
  confirm: '확인',
  close: '닫기',
} as const
