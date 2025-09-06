# GitHub Actions 发布工作流

本目录包含用于自动化版本管理和发布的 GitHub Actions 工作流。

## Create Release 工作流

`create-release.yml` 工作流用于创建新版本发布。它可以：

1. 根据语义化版本规则升级版本号（patch, minor, major）
2. 生成变更日志
3. 创建 GitHub Release
4. 构建和发布Python源码包
5. 自动更新分支版本

## 开发工作流程

在使用GitHub Actions发布之前，需要按照以下步骤进行开发：

### 1. 日常开发

在dev分支上进行开发：
```bash
git checkout dev

# 开发功能...

# 提交更改
git add .
git commit -m "feat: 添加了新功能"
git push origin dev
```

### 2. 创建开发版本

在完成开发并准备发布时，需要创建开发版本标签作为发布的起点。

**使用项目提供的脚本（推荐）**

项目在 `.github/scripts/` 目录下提供了版本管理脚本：

```bash
# 更新为开发版本（添加日期和git哈希）
python .github/scripts/update_dev_version.py

# 提交并推送开发版本
git add pyproject.toml
git commit -m "chore: update to dev version"
git push origin dev

# 创建开发版本标签
VERSION=$(python -c "import toml; print(toml.load('pyproject.toml')['project']['version'])")
git tag $VERSION
git push origin $VERSION
```

这会生成类似 `0.0.1-dev.20250906+abc123` 格式的版本号。

**手动创建标签（备选方案）**

如果需要手动创建标签，可以使用以下命令：

```bash
# Linux/Mac终端
VERSION=0.0.1
DATE=$(date +%Y%m%d)
COMMIT=$(git rev-parse --short HEAD)
git tag $VERSION-dev.$DATE+$COMMIT
git push origin $VERSION-dev.$DATE+$COMMIT

# Windows PowerShell
$VERSION="0.0.1"
$DATE=Get-Date -Format "yyyyMMdd"
$COMMIT=(git rev-parse --short HEAD)
git tag "$VERSION-dev.$DATE+$COMMIT"
git push origin "$VERSION-dev.$DATE+$COMMIT"
```

## 自动化发布流程

运行GitHub Actions工作流后，以下步骤将自动执行：

1. **创建发布分支**：基于选择的开发版本标签创建发布分支
2. **自动版本升级**：使用 `update_main_version.py` 脚本根据发布类型自动更新正式版本号
3. **生成变更日志**：自动收集提交记录并按类型分组
4. **构建和发布**：构建Python包并创建GitHub Release
5. **分支管理**：合并到main分支并自动更新dev分支
6. **自动开发版本**：使用 `update_dev_version.py` 脚本为dev分支生成新的开发版本号

## 使用方法

### 1. 触发工作流

1. 在 GitHub 上，转到 "Actions" 选项卡
2. 选择 "Create Release" 工作流
3. 点击 "Run workflow" 按钮

### 2. 输入参数

- **开发版本标签（devTag）**：要基于哪个开发版本标签创建发布
  - 格式示例：`0.0.1-dev.20250906+abc123`
  - 其中 `abc123` 为 git commit 短哈希

- **发布类型（releaseType）**：选择版本更新类型
  - `patch`：修复版本，如 0.0.1 → 0.0.2
  - `minor`：次要版本，如 0.0.1 → 0.1.0
  - `major`：主要版本，如 0.0.1 → 1.0.0

### 3. 执行发布

点击 "Run workflow" 开始执行自动化发布流程。

## 工作流详细步骤

工作流会按以下顺序执行：

1. **环境准备**
   - 检出指定的开发版本标签
   - 设置Python环境和依赖

2. **版本管理**
   - 创建发布分支
   - 使用 `update_main_version.py` 自动更新版本号

3. **发布准备**
   - 生成从上一个版本到新版本的变更日志
   - 构建 Python 源码包和wheel包

4. **发布执行**
   - 创建 GitHub Release 并上传构建产物
   - 合并发布分支到 main 分支
   - 创建并推送版本标签

5. **后续更新**
   - 使用 `update_dev_version.py` 自动更新 dev 分支版本号
   - 清理临时分支

## 版本管理脚本

项目提供了两个核心的版本管理脚本：

### `update_main_version.py` - 正式版本管理
```bash
# 升级补丁版本 (0.0.1 -> 0.0.2)
python .github/scripts/update_main_version.py --type patch

# 升级次版本 (0.0.1 -> 0.1.0)  
python .github/scripts/update_main_version.py --type minor

# 升级主版本 (0.0.1 -> 1.0.0)
python .github/scripts/update_main_version.py --type major
```

### `update_dev_version.py` - 开发版本管理
```bash
# 更新为开发版本
python .github/scripts/update_dev_version.py
```

## 提交规范

为了最大化变更日志的价值，建议按照以下规范进行提交：

- `feat: 添加了新功能` - 新功能
- `fix: 修复了某个bug` - 修复
- `docs: 更新了文档` - 文档更新
- `refactor: 重构了某部分代码` - 代码重构
- `chore: 更新构建脚本` - 构建过程或辅助工具的变动
- `test: 添加测试用例` - 测试

这样在生成变更日志时，可以自动按类别分组提交记录。

## 版本号格式

### 正式版本
- 格式：`X.Y.Z`
- 示例：`0.0.1`, `1.2.3`

### 开发版本
- 格式：`X.Y.Z-dev.YYYYMMDD+hash`
- 示例：`0.0.1-dev.20250906+abc123`
- 符合 PEP 440 标准

## 依赖要求

版本管理脚本需要安装 `toml` 库：

```bash
pip install toml
```

## 故障排除

### 常见问题

1. **标签已存在错误**
   - 检查是否已经创建了相同的开发版本标签
   - 使用 `git tag -l` 查看所有标签

2. **权限错误**
   - 确保 GitHub Actions 有足够的权限创建 releases
   - 检查 `GITHUB_TOKEN` 权限设置

3. **合并冲突**
   - 工作流会尝试自动解决 `pyproject.toml` 的冲突
   - 其他文件的冲突需要手动解决

4. **构建失败**
   - 检查 `requirements.txt` 中的依赖是否正确
   - 确保代码通过所有测试

### 调试技巧

- 查看 GitHub Actions 的详细日志
- 使用 `git log --oneline` 检查提交历史
- 验证标签是否正确创建：`git tag -l | grep dev`
