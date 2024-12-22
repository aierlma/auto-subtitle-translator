import json, time, asyncio, os, traceback
from opencc import OpenCC
from typing import Optional
from sys import exit
from random import choice
from GalTransl import LOGGER, LANG_SUPPORTED
from GalTransl.ConfigHelper import CProjectConfig, CProxyPool
from GalTransl.CSentense import CSentense, CTransList
from GalTransl.Cache import get_transCache_from_json, save_transCache_to_json
from GalTransl.Dictionary import CGptDict
from GalTransl.Backend.Prompts import Sakura_TRANS_PROMPT, Sakura_SYSTEM_PROMPT,Sakura_TRANS_PROMPT010,Sakura_SYSTEM_PROMPT010


class CSakuraTranslate:
    # init
    def __init__(
        self,
        config: CProjectConfig,
        eng_type: str,
        proxy_pool: Optional[CProxyPool],
    ):
        self.eng_type = eng_type
        self.last_file_name = ""
        self.restore_context_mode = config.getKey("gpt.restoreContextMode")
        self.retry_count = 0

        # 跳过重试
        if val := config.getKey("skipRetry"):
            self.skipRetry = val
        else:
            self.skipRetry = False
        # 流式输出模式
        if val := config.getKey("gpt.streamOutputMode"):
            self.streamOutputMode = val
        else:
            self.streamOutputMode = False
        # 多线程关闭流式输出
        if val := config.getKey("workersPerProject"):
            if val > 1:
                self.streamOutputMode = False
        # 代理
        if config.getKey("internals.enableProxy") == True:
            self.proxyProvider = proxy_pool
        else:
            self.proxyProvider = None
            LOGGER.warning("不使用代理")

        # 现在只有简体
        self.opencc = OpenCC("t2s.json")

        self.init_chatbot(eng_type=eng_type, config=config)  # 模型初始化

        pass

    def init_chatbot(self, eng_type, config: CProjectConfig):
        if eng_type == "sakura-009":
            from GalTransl.Backend.revChatGPT.V3 import Chatbot as ChatbotV3

            endpoint = config.getBackendConfigSection("Sakura").get("endpoint")
            if endpoint.endswith("/"):
                endpoint = endpoint[:-1]

            self.chatbot = ChatbotV3(
                api_key="sk-114514",
                system_prompt=Sakura_SYSTEM_PROMPT,
                engine="gpt-3.5-turbo",
                api_address=endpoint + "/v1/chat/completions",
                timeout=60,
            )
            self.chatbot.update_proxy(
                self.proxyProvider.getProxy().addr if self.proxyProvider else None  # type: ignore
            )
            self.trans_prompt = Sakura_TRANS_PROMPT
            self.transl_style = "auto"
            self._current_style = "precies"
            self._set_gpt_style("precise")
        if eng_type == "sakura-010":
            from GalTransl.Backend.revChatGPT.V3 import Chatbot as ChatbotV3

            endpoint = config.getBackendConfigSection("Sakura").get("endpoint")
            if endpoint.endswith("/"):
                endpoint = endpoint[:-1]

            self.chatbot = ChatbotV3(
                api_key="sk-114514",
                system_prompt=Sakura_SYSTEM_PROMPT010,
                engine="gpt-3.5-turbo",
                api_address=endpoint + "/v1/chat/completions",
                timeout=60,
            )
            self.chatbot.update_proxy(
                self.proxyProvider.getProxy().addr if self.proxyProvider else None  # type: ignore
            )
            self.trans_prompt = Sakura_TRANS_PROMPT010
            self.transl_style = "auto"
            self._current_style = "precies"
            self._set_gpt_style("precise")

    async def translate(self, trans_list: CTransList, gptdict=""):
        input_list = []
        max_len = 0
        for i, trans in enumerate(trans_list):
            # 处理换行
            tmp_text = trans.post_jp.replace("\r\n", "\\n").replace("\n", "\\n")
            # 有name
            if trans.speaker != "":
                tmp_text = f"{trans.speaker}「{tmp_text}」"
            input_list.append(tmp_text)
            max_len = max(max_len, len(tmp_text))
        input_str = "\n".join(input_list).strip("\n")
        
        # 检测退化阈值
        self.MAX_REPETITION_CNT = max(max_len + 5, 30)

        prompt_req = self.trans_prompt
        prompt_req = prompt_req.replace("[Input]", input_str)
        prompt_req = prompt_req.replace("[Glossary]", gptdict)

        once_flag = False

        while True:  # 一直循环，直到得到数据
            try:
                LOGGER.info("->输入：\n" + prompt_req + "\n")
                resp = ""
                last_data = ""
                repetition_cnt = 0
                degen_flag = False
                self._del_previous_message()
                ask_stream = self.chatbot.ask_stream_async(prompt_req)
                async for data in ask_stream:
                    if self.streamOutputMode:
                        print(data, end="", flush=True)
                    resp += data
                    # 检测是否反复重复输出同一内容，如果超过一定次数，则判定为退化并打断。
                    last_data, repetition_cnt, degen_flag = self.check_degen_in_process(
                        last_data, data, repetition_cnt
                    )
                    if degen_flag:
                        await ask_stream.aclose()
                        break
                # print(data, end="\n")
                if not self.streamOutputMode:
                    LOGGER.info("->输出：\n" + resp)
                else:
                    print("")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                str_ex = str(ex).lower()
                traceback.print_exc()
                self._del_last_answer()
                LOGGER.info("-> 报错:%s, 即将重试" % ex)
                await asyncio.sleep(3)
                continue

            result_list = resp.strip("\n").split("\n")
            # fix trick
            if result_list[0] == "——":
                result_list.pop(0)

            i = -1
            result_trans_list = []
            error_flag = False
            error_message = ""

            if degen_flag:
                error_message = f"-> 生成过程中检测到大概率为退化的特征"
                error_flag = True

            elif len(result_list) != len(trans_list):
                error_message = f"-> 翻译结果与原文长度不一致"
                error_flag = True

            for line in result_list:
                if error_flag:
                    break
                i += 1
                # 本行输出不应为空
                if trans_list[i].post_jp != "" and line == "":
                    error_message = f"-> 第{i+1}句空白"
                    error_flag = True
                    break

                # 提取对话内容
                if trans_list[i].speaker != "":
                    if "「" in line:
                        line = line[line.find("「") + 1 :]
                    if line.endswith("」"):
                        line = line[:-1]
                    if line.endswith("」。") or line.endswith("」."):
                        line = line[:-2]
                # 统一简繁体
                line = self.opencc.convert(line)
                # 还原换行
                if "\r\n" in trans_list[i].post_jp:
                    line = line.replace("\\n", "\r\n")
                elif "\n" in trans_list[i].post_jp:
                    line = line.replace("\\n", "\n")

                # fix trick
                if line.startswith("："):
                    line = line[1:]

                trans_list[i].pre_zh = line
                trans_list[i].post_zh = line
                trans_list[i].trans_by = "Sakura v0.9"
                result_trans_list.append(trans_list[i])

            if error_flag:
                if self.skipRetry:
                    self.reset_conversation()
                    LOGGER.warning("-> 解析出错但跳过本轮翻译")
                    i = 0 if i < 0 else i
                    while i < len(trans_list):
                        trans_list[i].pre_zh = "Failed translation"
                        trans_list[i].post_zh = "Failed translation"
                        trans_list[i].trans_by = "Sakura v0.9(Failed)"
                        result_trans_list.append(trans_list[i])
                        i = i + 1
                else:
                    LOGGER.error(f"-> 错误的输出：{error_message}")
                    # 删除上次回答与提问
                    self._del_last_answer()
                    await asyncio.sleep(1)
                    # 切换模式
                    if self.transl_style == "auto":
                        self._set_gpt_style("normal")
                    # 先增加frequency_penalty参数重试再进行二分
                    if not once_flag:
                        once_flag = True
                        continue
                    # 可拆分先对半拆
                    if len(trans_list) > 1:  
                        LOGGER.warning("-> 对半拆分重试")
                        return await self.translate(
                            trans_list[: len(trans_list) // 2], gptdict
                        )
                    # 拆成单句后，才开始计算重试次数
                    self.retry_count += 1
                    # 5次重试则填充原文
                    if self.retry_count >= 5:
                        LOGGER.error(f"-> 单句循环重试{self.retry_count}次出错，填充原文")
                        i = 0 if i < 0 else i
                        while i < len(trans_list):
                            trans_list[i].pre_zh = trans_list[i].post_jp
                            trans_list[i].post_zh = trans_list[i].post_jp
                            trans_list[i].trans_by = "Sakura v0.9(Failed)"
                            result_trans_list.append(trans_list[i])
                            i = i + 1
                        return i, result_trans_list
                    # 2次重试则重置会话
                    elif self.retry_count % 2 == 0:
                        self.reset_conversation()
                        LOGGER.warning(f"-> 单句循环重试{self.retry_count}次出错，重置会话")
                        continue
                    continue
            else:
                self.retry_count = 0
            if self.transl_style == "auto":
                self._set_gpt_style("precise")
            return i + 1, result_trans_list

    async def batch_translate(
        self,
        filename,
        cache_file_path,
        trans_list: CTransList,
        num_pre_request: int,
        retry_failed: bool = False,
        gpt_dic: CGptDict = None,
        proofread: bool = False,
        retran_key: str = "",
    ) -> CTransList:
        _, trans_list_unhit = get_transCache_from_json(
            trans_list,
            cache_file_path,
            retry_failed=retry_failed,
            proofread=False,
            retran_key=retran_key,
        )

        if len(trans_list_unhit) == 0:
            return []
        # 新文件重置chatbot
        if self.last_file_name != filename:
            self.reset_conversation()
            self.last_file_name = filename
            LOGGER.info(f"-> 开始翻译文件：{filename}")
        i = 1 # 修改自原作者
        if self.restore_context_mode and len(self.chatbot.conversation["default"]) == 1:
            self.restore_context(trans_list_unhit, num_pre_request)

        trans_result_list = []
        len_trans_list = len(trans_list_unhit)
        transl_step_count = 0
        progress_bar = atqdm(
            total=len_trans_list,
            desc=f"Translating {filename}",
            unit="line",
            dynamic_ncols=True,
            leave=False,
            file=sys.stdout,
        )
        while i < len_trans_list-2 and i>=1:
            await asyncio.sleep(1)

            trans_list_split = trans_list_unhit[i-1 : i + num_pre_request+1] # 前加一句后加一句，修改自原作者
            dic_prompt = (
                gpt_dic.gen_prompt(trans_list_split, type="sakura")
                if gpt_dic != None
                else ""
            )
            num, trans_result = await self.translate(trans_list_split, dic_prompt)

            i += num-2 if num-2 > 0 else 0 # 修改自原作者
            LOGGER.info("".join([repr(tran) for tran in trans_result]))
            trans_result_list += trans_result[1:-1] # 修改自原作者
            save_transCache_to_json(trans_list, cache_file_path)
            LOGGER.info(f"{filename}: {len(trans_result_list)}/{len_trans_list}")

        return trans_result_list

    def reset_conversation(self):
        self.chatbot.reset()

    def _del_previous_message(self) -> None:
        """删除历史消息，只保留最后一次的翻译结果，节约tokens"""
        last_assistant_message = None
        for message in self.chatbot.conversation["default"]:
            if message["role"] == "assistant":
                last_assistant_message = message
        system_message = self.chatbot.conversation["default"][0]
        if last_assistant_message != None:
            self.chatbot.conversation["default"] = [
                system_message,
                last_assistant_message,
            ]

    def _del_last_answer(self):
        # 删除上次输出
        if self.chatbot.conversation["default"][-1]["role"] == "assistant":
            self.chatbot.conversation["default"].pop()
        elif self.chatbot.conversation["default"][-1]["role"] is None:
            self.chatbot.conversation["default"].pop()
        # 删除上次输入
        if self.chatbot.conversation["default"][-1]["role"] == "user":
            self.chatbot.conversation["default"].pop()

    def _set_gpt_style(self, style_name: str):
        if self._current_style == style_name:
            return
        self._current_style = style_name
        if self.transl_style == "auto":
            LOGGER.info(f"-> 自动切换至{style_name}参数预设")
        else:
            LOGGER.info(f"-> 使用{style_name}参数预设")

        if style_name == "precise":
            temperature, top_p = 0.1, 0.3
            frequency_penalty, presence_penalty = 0.0, 0.0
        elif style_name == "normal":
            temperature, top_p = 0.3, 0.3
            frequency_penalty, presence_penalty = 0.15, 0.0

        self.chatbot.temperature = temperature
        self.chatbot.top_p = top_p
        self.chatbot.frequency_penalty = frequency_penalty
        self.chatbot.presence_penalty = presence_penalty

    def restore_context(self, trans_list_unhit: CTransList, num_pre_request: int):
        if trans_list_unhit[0].prev_tran == None:
            return
        tmp_context = []
        num_count = 0
        current_tran = trans_list_unhit[0].prev_tran
        while current_tran != None:
            if current_tran.pre_zh == "":
                current_tran = current_tran.prev_tran
                continue
            if current_tran.speaker != "":
                tmp_text = f"{current_tran.speaker}「{current_tran.pre_zh}」"
            else:
                tmp_text = f"{current_tran.pre_zh}"
            tmp_context.append(tmp_text)
            num_count += 1
            if num_count >= num_pre_request:
                break
            current_tran = current_tran.prev_tran

        tmp_context.reverse()
        json_lines = "\n".join(tmp_context)
        self.chatbot.conversation["default"].append(
            {
                "role": "assistant",
                "content": f"{json_lines}",
            }
        )
        LOGGER.info("-> 恢复了上下文")

    def check_degen_in_process(self, last_data: str, data: str, repetition_cnt: int):
        degen_flag = False
        if last_data == data:
            repetition_cnt += 1
        else:
            repetition_cnt = 0
        if repetition_cnt > self.MAX_REPETITION_CNT:
            degen_flag = True
        last_data = data
        return last_data, repetition_cnt, degen_flag


if __name__ == "__main__":
    pass
