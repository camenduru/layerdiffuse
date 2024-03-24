import torch

from refiners.fluxion.utils import load_from_safetensors, manual_seed, no_grad, images_to_tensor, tensor_to_image
from refiners.foundationals.latent_diffusion.lora import SDLoraManager
from refiners.foundationals.latent_diffusion.stable_diffusion_xl import (
    StableDiffusion_XL,
)

from layerdiffuse.models.models import UNet1024Refiners, TransparentVAEDecoder
from utils.utils import modify_dict

from PIL import Image

torch.autocast("cuda", torch.float16).__enter__()
#Load SDXL
sdxl = StableDiffusion_XL(device="cuda", dtype=torch.float16)
sdxl.clip_text_encoder.load_from_safetensors("sdxl-weights/text_encoder.safetensors")
sdxl.unet.load_from_safetensors("sdxl-weights/unet.safetensors")
sdxl.lda.load_from_safetensors("sdxl-weights/lda.safetensors")

#Load LoRA weights from disk and inject them into target
manager = SDLoraManager(sdxl)

ld_lora_weights = load_from_safetensors("layer_xl_transparent_attn.safetensors")
ld_lora_weights_modified = modify_dict(ld_lora_weights)

#sci_fi_lora_weights = load_from_safetensors("sci-fi-lora.safetensors")
try:
    manager.add_loras("ld-lora", tensors=ld_lora_weights_modified, unet_inclusions= ["Attention", "SelfAttention"])
except:
    pass
# Load Layer diffuse decoder
# ld_decoder = UNet1024Refiners(out_channels=4)
# ld_decoder.load_from_safetensors("vae_transparent_decoder.safetensors")
# ld_decoder = ld_decoder.to("cuda", torch.float16)

ld_decoder = TransparentVAEDecoder("vae_transparent_decoder.safetensors")


# Hyperparameters
#prompt = "a futuristic magical panda with a purple glow, cyberpunk"
prompt = "a unique realistic red apple"
seed = 42
sdxl.set_inference_steps(50, first_step=0)
sdxl.set_self_attention_guidance(
    enable=True, scale=0.75
)  # Enable self-attention guidance to enhance the quality of the generated images

with no_grad():
    clip_text_embedding, pooled_text_embedding = sdxl.compute_clip_text_embedding(
        text=prompt + ", best quality, high quality",
        negative_text="monochrome, lowres, bad anatomy, worst quality, low quality",
    )
    time_ids = sdxl.default_time_ids

    manual_seed(seed=seed)

    
    x = sdxl.init_latents((1024, 1024)).to(sdxl.device, sdxl.dtype)
    #ld_decoder.set_context("unet1024", {"latent": x})

    # Diffusion process
    for step in sdxl.steps:
        if step % 10 == 0:
            print(f"Step {step}")
        x = sdxl(
            x,
            step=step,
            clip_text_embedding=clip_text_embedding,
            pooled_text_embedding=pooled_text_embedding,
            time_ids=time_ids,
        )
    latent = x
    pixel = sdxl.lda.decode_latents(x)
    pixel.save("outputs/origin_sdxl.png")

    pixel = images_to_tensor([pixel], dtype = torch.float16, device= "cuda")
    #transparent_image = ld_decoder(predicted_tensor)
    transparent_image = ld_decoder.run(pixel, latent)
    tensor_to_image(transparent_image).save("outputs/transparent_sdxl.png")

    pixel = Image.open("pixels.png")
    latent = Image.open("latent.png")

    pixel = images_to_tensor([pixel], dtype = torch.float16, device= "cuda")
    latent = images_to_tensor([latent], dtype = torch.float16, device= "cuda")

    #transparent_image = ld_decoder(images_to_tensor([image_prompt], dtype = torch.float16, device= "cuda"))
    transparent_image = ld_decoder.run(pixel, latent)
    tensor_to_image(transparent_image.detach()).save("outputs/transparent_sdxl_from_image.png")



