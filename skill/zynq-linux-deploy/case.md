# 来源、失败观察与验证效果

来源：2026-11-03“添加板端演示模式”协作轮次，附 [真实交互摘录](../evidence/demo_collaboration.json) 与 [历史部署结果](../evidence/deploy_result.json)。摘录只含该轮用户和助手消息，不是完整工具日志，也不把助手自述当独立验证。

失败触发：用户反馈切换按键不见了。观察到普通检测页与演示页不同，模型列表稍晚到达时也需要正确创建按钮。网络不可达期间先查连接，没有把缺失截图直接当成 UI 缺陷证据。

方法：区分状态/页面与渲染问题，检查提前开页、模型切换、退出重进及进程重启；RAM 验证之后安装，核对板端和交付文件哈希。

历史结果记录 installed=true、defaultDemoOnPanelStart=true、zeroNewRecords=true、formalFilesUnchanged=true、SLCR=0、ioErrors=[]，fsync/读回 4194304 字节。coldBootVerified=false，因此不能声称断电冷启动已验证。formalFilesUnchanged 指试验记录中的业务正式文件检查，不表示安装没有改变程序文件。

适用于具有异步状态/UI 和可回退部署机制的其他终端；按钮数、默认页、设备地址不是通用契约。本次仅复制当时 JSON 并核查字段，没有连接板卡、重放 UI 或证明 SD 根因已解决。
