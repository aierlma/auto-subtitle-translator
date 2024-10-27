import os
import sys
import shutil
from prompt2srt import make_srt, make_lrc
from srt2prompt import make_prompt

def translate_srt(input_srt, sakura_address=None):
    """使用Sakura翻译SRT文件"""
    print("正在初始化项目文件夹...")
    
    # 创建必要的目录
    os.makedirs('project/cache', exist_ok=True)
    os.makedirs('project/gt_input', exist_ok=True)
    
    # 复制输入文件到工作目录
    target_srt = os.path.join('project/cache', os.path.basename(input_srt))
    shutil.copy2(input_srt, target_srt)
    
    # 转换srt为json格式
    print("正在进行字幕转换...")
    output_file_path = os.path.join('project/gt_input', os.path.basename(input_srt).replace('.srt','.json'))
    make_prompt(target_srt, output_file_path)
    print("字幕转换完成！")
    
    # 配置翻译设置
    print("正在进行翻译配置...")
    config_path = 'project/config.yaml'
    if not os.path.exists(config_path):
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write('''GalTransl:
  proxy:
    enableProxy: false
    proxies:
      - address: ""
  GPT35:
    tokens:
      - token: ""
    defaultEndpoint: ""
    rewriteModelName: ""
  Sakura:
    endpoint: ""''')
    
    if sakura_address: # if sakura_address is None, use the default endpoint 8080
        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for idx, line in enumerate(lines):
            if 'Sakura' in line:
                lines[idx+1] = f"    endpoint: {sakura_address}\n"
        
        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    
    # 执行翻译
    print("正在进行翻译...")
    from GalTransl.__main__ import worker
    worker('project', 'config.yaml', 'sakura-010', show_banner=False)
    
    # 生成翻译后的字幕文件
    print("正在生成字幕文件...")
    output_json = output_file_path.replace('gt_input','gt_output')
    output_srt = os.path.join('project/cache', os.path.splitext(os.path.basename(input_srt))[0] + '.zh.srt')
    make_srt(output_json, output_srt)
    
    # 同时生成lrc格式
    output_lrc = os.path.join('project/cache', os.path.splitext(os.path.basename(input_srt))[0] + '.lrc')
    make_lrc(output_json, output_lrc)
    print("字幕文件生成完成！")
    
    return output_srt

def main():
    if len(sys.argv) < 2:
        print("使用方法: python cli.py <srt文件路径> [sakura_address]")
        sys.exit(1)
    
    input_srt = sys.argv[1]
    sakura_address = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(input_srt):
        print(f"错误: 文件 {input_srt} 不存在")
        sys.exit(1)
    
    # try:
    output_path = translate_srt(input_srt, sakura_address)
    print(f"\n处理完成!")
    print(f"翻译后的字幕文件保存在: {output_path}")
    # except Exception as e:
    #     print(f"处理过程中出现错误: {str(e)}")
    #     sys.exit(1)

if __name__ == "__main__":
    main()
