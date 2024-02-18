from PIL import Image
import numpy as np
import torch
from rembg import remove, new_session
from extras.GroundingDINO.util.inference import default_groundingdino
import enhanced.translator as translator
import enhanced.enhanced_parameters as enhanced_parameters

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def run_grounded_sam(input_image, text_prompt, box_threshold, text_threshold):

    # run grounding dino model
    boxes, _ = default_groundingdino(
        image=np.array(input_image),
        caption=text_prompt,
        box_threshold=box_threshold,
        text_threshold=text_threshold
    )

    return boxes.xyxy


def generate_mask_from_image(image, mask_model, extras):
    if image is None:
        return

    if 'image' in image:
        image = image['image']

    if mask_model == 'sam':
        if enhanced_parameters.translation_timing != 'No translate':
            extras['sam_prompt_text'] = translator.convert(extras['sam_prompt_text'], enhanced_parameters.translation_methods)
 
        boxes = run_grounded_sam(Image.fromarray(image), extras['sam_prompt_text'], box_threshold=extras['box_threshold'], text_threshold=extras['text_threshold'])
        extras['sam_prompt'] = []
        for idx, box in enumerate(boxes):
            extras['sam_prompt'] += [{"type": "rectangle", "data": box.tolist()}]

    return remove(
        image,
        session=new_session(mask_model, **extras),
        only_mask=True,
        **extras
    )
