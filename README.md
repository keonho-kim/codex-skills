# Codex Skills

## SKILL 설치 (일반)
SKILL은 `SKILL.md`가 포함된 폴더 전체를 Codex 스킬 디렉터리로 복사해서 설치합니다.

```bash
# 기본 위치: ~/.codex/skills (CODEX_HOME/skills)
mkdir -p ~/.codex/skills
cp -R <skill-folder> ~/.codex/skills/
```

설치 확인:

```bash
ls ~/.codex/skills/<skill-folder>
```

## Codex Swarm
기능: 여러 하위 디렉터리에서 `codex exec` 작업을 JSON 배치로 안전하게 병렬 실행.

설치:

```bash
mkdir -p ~/.codex/skills
cp -R codex-swarm ~/.codex/skills/
```
