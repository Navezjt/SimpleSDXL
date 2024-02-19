import gradio as gr
import os
import math
import json
import copy
import modules.util as util
import modules.config as config
import enhanced.toolbox as toolbox
from lxml import etree




# app context
images_list = {}
images_list_keys = []
images_prompt = {}
images_prompt_keys = []
images_ads = {}
history_path = ""
def refresh_output_list(max_per_page, cookie='default'):
    global history_path
    history_path = os.path.join(config.path_outputs, cookie)
    # history_path = os.path.join(config.path_outputs, 'default')
    if not os.path.exists(history_path):
        os.mkdir(history_path)
    # print(f"[LOGINFO] {history_path}")
    
    listdirs = [f for f in os.listdir(history_path) if f!="embed" and os.path.isdir(os.path.join(history_path,f))]
    if listdirs is None:
        return None
    listdirs1 = listdirs.copy()
    for index in listdirs:
        path_gallery = os.path.join(history_path, index)
        nums = len(util.get_files_from_folder(path_gallery, ['.png'], None))
        if nums > max_per_page:
            for i in range(1,math.ceil(nums/max_per_page)+1):
                listdirs1.append(index + "/" + str(i))
            listdirs1.remove(index)
    output_list = sorted([f[2:] for f in listdirs1], reverse=True)
    print(f'[Gallery] Refresh_output_catalog: loaded {len(output_list)} images_catalogs.')
    return output_list


def images_list_update(choice, state_params):
    if "__output_list" not in state_params.keys():
        return gr.update(), gr.update(), state_params
    output_list = state_params["__output_list"]
    if choice is None and len(output_list) > 0:
        choice = output_list[0]
    images_gallery = get_images_from_gallery_index(choice, state_params["__max_per_page"])
    state_params.update({"prompt_info": [choice, 0]})
    return gr.update(value=images_gallery), gr.update(open=False, visible=len(output_list)>0), state_params


def select_index(choice, state_params, evt: gr.SelectData):
    if "__output_list" in state_params.keys():
        state_params.update({"infobox_state": 0})
        state_params.update({"note_box_state": ['',0,0]})
    print(f'[Gallery] Selected_gallery_catalog: change image catalog:{choice}.')
    return [gr.update(visible=True)] + [gr.update(visible=False)] * 4 + [gr.update(interactive=True) , state_params]


def select_gallery(choice, state_params, backfill_prompt, evt: gr.SelectData):
    if "__output_list" not in state_params.keys():
        return  [gr.update()] * 7 + [state_params]
    state_params.update({"note_box_state": ['',0,0]})
    state_params.update({"prompt_info": [choice, evt.index]})
    if choice is None and len(state_params["__output_list"]) > 0:
        choice = state_params["__output_list"][0]
    result = get_images_prompt(choice, evt.index, state_params["__max_per_page"], True)
    #print(f'[Gallery] Selected_gallery: selected index {evt.index} of {choice} images_list:{result["Filename"]}.')
    if backfill_prompt:
        return [gr.update(value=toolbox.make_infobox_markdown(result)), gr.update(value=result["Prompt"]), gr.update(value=result["Negative Prompt"])] + [gr.update(visible=False)] * 4 + [state_params]
    else:
        return [gr.update(value=toolbox.make_infobox_markdown(result)), gr.update(), gr.update()] + [gr.update(visible=False)] * 4 + [state_params]

def select_gallery_progress(state_params, evt: gr.SelectData):
    state_params.update({"note_box_state": ['',0,0]})
    state_params.update({"prompt_info": [None, evt.index]})
    # output_list = state_params["__output_list"]
    # print(f"[LOGINFO] {output_list}")
    result = get_images_prompt(state_params["__output_list"][0], evt.index, state_params["__max_per_page"])
    return [gr.update(value=toolbox.make_infobox_markdown(result), visible=False)] + [gr.update(visible=False)] * 4 + [state_params]


def get_images_from_gallery_index(choice, max_per_page):
    global images_list, history_path

    page = 0
    _page = choice.split("/")
    if len(_page) > 1:
        choice = _page[0]
        page = int(_page[1])

    images_gallery = refresh_images_catalog(choice)
    nums = len(images_gallery)
    if page > 0:
        page = abs(page-math.ceil(nums/max_per_page))+1
        if page*max_per_page < nums:
            images_gallery = images_list[choice][(page-1)*max_per_page:page*max_per_page]
        else:
            images_gallery = images_list[choice][nums-max_per_page:]
    images_gallery = [os.path.join(os.path.join(history_path, '20' + choice), f) for f in images_gallery]
    #print(f'[Gallery]Get images from index: choice={choice}, page={page}, images_gallery={images_gallery}')
    return images_gallery


def refresh_images_catalog(choice: str, passthrough = False):
    global images_list, images_list_keys, history_path

    if not passthrough and choice in images_list_keys:
        images_list_keys.remove(choice)
        images_list_keys.append(choice)
        #print(f'[Gallery] Refresh_images_list: hit cache {len(images_list[choice])} image_items of {choice}.')
        return images_list[choice]

    images_list_new = sorted([f for f in util.get_files_from_folder(os.path.join(history_path, '20' + choice), ['.png'], None)], reverse=True)
    if len(images_list_new)==0:
        parse_html_log(choice, passthrough)
        if choice in images_list_keys:
            images_list_keys.pop(images_list_keys.index(choice))
            images_list.pop(choice)
        return []
    if choice in images_list_keys:
        images_list_keys.pop(images_list_keys.index(choice))
    if len(images_list.keys())>15:
        images_list.pop(images_list_keys.pop(0))
    images_list.update({choice: images_list_new})
    images_list_keys.append(choice)
    parse_html_log(choice, passthrough)
    print(f'[Gallery] Refresh_images_catalog: loaded {len(images_list[choice])} image_items of {choice}.')
    return images_list[choice]


def get_images_prompt(choice, selected, max_per_page, display_index=False):
    global images_list, images_prompt, images_prompt_keys, images_ads

    if choice is None:
        return None
    page = 0
    _page = choice.split("/")
    if len(_page) > 1:
        choice = _page[0]
        page = int(_page[1])
    page_choice = page
    page_index = selected
    parse_html_log(choice)
    nums = len(images_list[choice])
    if page > 0:
        page = abs(page-math.ceil(nums/max_per_page))+1
        if page*max_per_page < nums:
            selected = (page-1)*max_per_page + selected
        else:
            selected = nums-max_per_page + selected
    images_prompt_keys.remove(choice)
    images_prompt_keys.append(choice)
    filename = images_list[choice][selected]
    metainfo = {"Filename": filename} if filename not in images_prompt[choice].keys() else images_prompt[choice][filename]
    if display_index:
        print(f'[Gallery] The image selected: catalog={choice}, page={page_choice}, in_page={page_index}, in_catalog={selected}, filename={filename}')
    if choice in images_ads.keys() and filename in images_ads[choice].keys():
        metainfo.update({"Advanced_parameters": images_ads[choice][metainfo['Filename']]})
    return metainfo


def parse_html_log(choice: str, passthrough = False):
    global images_prompt, images_prompt_keys, images_ads, history_path
    
    choice = choice.split('/')[0]
    if not passthrough and choice in images_prompt_keys and images_prompt[choice]:
        images_prompt_keys.remove(choice)
        images_prompt_keys.append(choice)
        #print(f'[Gallery] Parse_html_log: hit cache {len(images_prompt[choice])} image_infos of {choice}.')
        return
    html_file = os.path.join(os.path.join(history_path, '20' + choice), 'log.html')
    html = etree.parse(html_file, etree.HTMLParser(encoding='utf-8'))
    prompt_infos = html.xpath('/html/body/div')
    images_prompt_list = {}
    for info in prompt_infos:
        text = info.xpath('.//p//text()')
        #print(f'log_parse_text1:{text}')
        if len(text)>20:
            def standardized(x):
                if x.startswith(', '):
                    x=x[2:]
                if x.endswith(': '):
                    x=x[:-2]
                if x==' ':
                    x=''
                return x
            text = list(map(standardized, info.xpath('.//p//text()')))
            if text[6]!='':
                text.insert(6, '')
            if text[8]=='':
                text.insert(8, '')
            info_dict={"Filename":text[0]}
            if text[3]=='':
                info_dict[text[1]] = text[2]
                info_dict[text[4]] = text[5]
                info_dict[text[7]] = text[8]
                for i in range(0,int(len(text)/2)-5):
                    info_dict[text[10+i*2]] = text[11+i*2]
            else:
                if text[4]!='Fooocus V2 Expansion':
                    del text[6]
                else:
                    text.insert(4, '')
                    if text[6]=='Styles':
                        text.insert(6, '')
                        del text[8]
                    else:
                        del text[7]
                for i in range(0,int(len(text)/2)-1):
                    info_dict[text[1+i*2]] = text[2+i*2]
        else:
            text = info.xpath('.//td//text()')
            #print(f'log_parse_text2:{text}')
            if len(text)>10:
                if text[2]=='\n' or text[2]=='\r\n':
                    text.insert(2, '')
                if text[5]=='\n' or text[5]=='\r\n':
                    text.insert(5, '')
                if text[8]=='\n' or text[8]=='\r\n':
                    text.insert(8, '')
                info_dict={"Filename":text[0]}
                for i in range(0,int(len(text)/3)):
                    if text[1+i*3].startswith("LoRA "):
                        [key, value] = text[2+i*3].split(':')
                        info_dict.update({"LoRA ["+key.strip()+"] weight": value.strip()})
                    else:
                        info_dict[text[1+i*3]] = text[2+i*3]
            else:
                print(f'[Gallery] Parse_html_log: Parse error for {choice}, file={html_file}\ntext:{info.xpath(".//text()")}')
        #print(f'{len(text)},info_dict={info_dict}')
        images_prompt_list.update({info_dict["Filename"]: info_dict})
    if len(images_prompt_list.keys())==0:
        if choice in images_prompt.keys():
            images_prompt_keys.pop(images_prompt_keys.index(choice))
            images_prompt.pop(choice)
            if choice in images_ads.keys():
                images_ads.pop(choice)
        return
    if choice in images_prompt_keys:
        images_prompt_keys.pop(images_prompt_keys.index(choice))
    if len(images_prompt.keys())>15:
        key = images_prompt_keys.pop(0)
        images_prompt.pop(key)
        if key in images_ads.keys():
            images_ads.pop(key)
    images_prompt.update({choice: images_prompt_list})
    images_prompt_keys.append(choice)
    
    dirname, filename = os.path.split(html_file)
    log_name = os.path.join(dirname, "log_ads.json")
    log_ext = {}
    if os.path.exists(log_name):
        with open(log_name, "r", encoding="utf-8") as log_file:
            log_ext.update(json.load(log_file))
    images_ads.update({choice: log_ext})
    
    print(f'[Gallery] Parse_html_log: loaded {len(images_prompt[choice])} image_infos of {choice}.')
    return


