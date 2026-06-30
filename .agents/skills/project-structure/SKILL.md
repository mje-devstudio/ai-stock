---
name: project-structure-guide
description: Guides file placement, directory structure, module roles, and codebase organization in the ai-stock project. Triggers when creating new files, rearranging modules, or analyzing code structure.
---

# 프로젝트 구조 및 모듈 배치 규칙 (ai-stock)

이 프로젝트는 키움증권 REST API 및 웹소켓을 연동한 자동매매 시스템입니다. 코드 작성 및 프로젝트 수정 시 아래의 디렉토리 구조와 규칙을 엄격히 준수하십시오.

## 1. 디렉토리 구조 및 역할 분담

새로운 파일을 생성하거나 기능을 추가할 때는 해당 기능의 역할에 맞는 디렉토리에 배치해야 합니다.

- **최상위 디렉토리 (`/`)**: 
  - 프로그램의 시작점(Entry Point)이 되는 메인 모듈(`main.py` 등) 및 전역 제어 로직만 위치해야 합니다.
  - 개별 기능(TR API, 텔레그램 명령어, 매매 전략 등)의 구현을 여기에 직접 추가하지 마십시오.
  
- **`api/` (API 호출)**:
  - 키움증권 REST API 호출 관련 모듈이 들어갑니다.
  - 기능(TR)별로 모듈을 분리하여 구현하십시오.
  
- **`realtime/` (실시간 데이터)**:
  - 웹소켓을 통한 실시간 시세/체결 데이터 수신 및 처리 관련 모듈을 정의합니다.
  
- **`telegram/` (텔레그램 연동)**:
  - 텔레그램 봇의 실행, 사용자 메시지 파싱, 메시지 전송 등 핵심 전송 로직이 위치합니다.
  - **`telegram/commands/`**: 텔레그램 봇의 개별 명령어 처리 모듈은 이 디렉토리에 명령어별로 독립된 파일로 작성되어야 합니다.
  
- **`trading/` (매매 전략)**:
  - 매매 전략 및 실제 주문 실행 로직이 구현되는 곳입니다. 
  - 다양한 투자/매매 알고리즘은 각각 이 디렉토리 내에 모듈별로 격리하여 구현하십시오.
  
- **`utils/` (유틸리티)**:
  - 프로젝트 전반에서 공통으로 사용되는 독립적이고 재사용 가능한 유틸리티 함수나 헬퍼 모듈을 작성합니다.
  
- **`config/` (설정 및 인증)**:
  - 정적 설정 파일 및 API 인증 정보를 관리합니다.
  - **`config/data/`**: 실행 중에 동적으로 변경되는 사용자/시스템 설정 데이터(JSON 형식)를 관리합니다.
    - 동적 설정은 `config/data/settings.json`에 저장하고 로드합니다.
    - 해당 설정의 기본값은 `config/data/settings-default.json`에 정의합니다.
    
- **`tr_docs/` (TR 명세)**:
  - 키움 REST API의 TR(Transaction) 명세서 문서 파일들을 모아두는 곳입니다.

## 2. 개발 및 설계 원칙

- **모듈화 및 관심사 분리**: 
  - 텔레그램 명령어에서 매매 전략을 직접 길게 구현하지 마십시오. 비즈니스 로직은 `trading/`에, 사용자 상호작용은 `telegram/`에 분리합니다.
  - REST API 요청은 반드시 `api/` 내부 모듈을 경유하도록 합니다.
- **설정 및 상태 관리**:
  - 하드코딩된 값 대신 `config/data/settings.json`을 사용해 설정을 동적으로 관리하십시오.
  - 새로운 설정 항목이 필요한 경우 `settings-default.json`에도 기본값을 함께 추가하십시오.
- **유틸리티 활용**:
  - 날짜 형식 변환, 공통 데이터 가공 등의 중복 코드를 지양하고 `utils/`에 공통 함수로 정의하여 재사용하십시오.
