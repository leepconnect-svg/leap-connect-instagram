"""
生成した画像を、外部の無料画像ホスト(ImgBB等)ではなく、
このGitHubリポジトリ自身にコミット&pushし、jsdelivr CDN経由で
Instagram Graph APIから読み込める公開URLを作る。

背景: ImgBB等の無料画像ホストは、Instagram側のクローラーからの
取得に安定して失敗するケースが確認された
("Media download has failed. The media URI doesn't meet our requirements.")。
GitHub + jsdelivrは世界的に広く使われている実績のあるCDNで、
Metaのクローラーからの取得実績も豊富なため、より信頼性が高い。

注意: この方式が機能するには、リポジトリが public である必要がある
(jsdelivr/raw.githubusercontentはprivateリポジトリの内容を配信できないため)。
GitHub Secretsに登録した資格情報自体はリポジトリの公開/非公開設定と無関係に
常に暗号化されて保護されるため、リポジトリをpublicにしても漏洩しない。
"""
import os
import re
import subprocess


def _run(args: list[str], cwd: str) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git コマンド失敗: {' '.join(args)}\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def _get_repo_slug(repo_root: str) -> str:
    env_repo = os.environ.get("GITHUB_REPOSITORY")  # GitHub Actionsが自動設定 "owner/repo"
    if env_repo:
        return env_repo
    url = _run(["git", "config", "--get", "remote.origin.url"], cwd=repo_root)
    m = re.search(r"github\.com[:/]+([^/]+/[^/.]+?)(\.git)?$", url)
    if not m:
        raise RuntimeError(f"GitHubリポジトリを特定できませんでした(remote.origin.url={url})")
    return m.group(1)


def _get_branch(repo_root: str) -> str:
    return os.environ.get("GITHUB_REF_NAME") or _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root)


def publish_images_to_github(image_paths: list[str], repo_root: str) -> list[str]:
    """画像ファイル群をリポジトリにcommit & pushし、jsdelivr経由の公開URL一覧を返す(投稿順)"""
    repo_root = os.path.abspath(repo_root)

    _run(["git", "config", "user.name", "github-actions[bot]"], cwd=repo_root)
    _run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=repo_root)

    rel_paths = [os.path.relpath(os.path.abspath(p), repo_root) for p in image_paths]

    _run(["git", "add", "-f", *rel_paths], cwd=repo_root)

    diff_check = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo_root)
    if diff_check.returncode != 0:  # 差分あり = コミットすべき内容がある
        _run(["git", "commit", "-m", "chore: publish post images [skip ci]"], cwd=repo_root)
        _run(["git", "pull", "--no-edit", "--rebase"], cwd=repo_root)
        _run(["git", "push"], cwd=repo_root)

    repo_slug = _get_repo_slug(repo_root)
    branch = _get_branch(repo_root)

    urls = []
    for rel in rel_paths:
        posix_rel = rel.replace(os.sep, "/")
        urls.append(f"https://cdn.jsdelivr.net/gh/{repo_slug}@{branch}/{posix_rel}")
    return urls
