/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars */
import {
  AngularNodeAppEngine,
  createNodeRequestHandler,
  isMainModule,
  writeResponseToNodeResponse,
} from '@angular/ssr/node';
import express from 'express';
import {join} from 'node:path';
import { GoogleGenAI, Type } from "@google/genai";

// Load environment variables from .env if available
if (typeof process.loadEnvFile === 'function') {
  try {
    process.loadEnvFile();
  } catch (e) {
    // Ignore if file not found
  }
}

const ai = new GoogleGenAI({
  apiKey: process.env['GEMINI_API_KEY'] || 'DUMMY_KEY',
  httpOptions: {
    headers: {
      'User-Agent': 'aistudio-build',
    }
  }
});

/**
 * Helper to convert Gemini API's uppercase schema Types to standard lowercase JSON schema types.
 */
function convertGeminiSchemaToStandard(schema: any): any {
  if (!schema) return schema;
  const newSchema = { ...schema };
  if (typeof newSchema.type === 'string') {
    newSchema.type = newSchema.type.toLowerCase();
  }
  if (newSchema.properties) {
    const newProps: any = {};
    for (const [k, v] of Object.entries(newSchema.properties)) {
      newProps[k] = convertGeminiSchemaToStandard(v);
    }
    newSchema.properties = newProps;
  }
  if (newSchema.items) {
    newSchema.items = convertGeminiSchemaToStandard(newSchema.items);
  }
  return newSchema;
}

/**
 * Universal helper to call an LLM (Gemini or OpenRouter) based on the env configuration.
 */
async function callLLM(options: {
  prompt: string;
  imagesBase64?: string[];
  responseSchema?: any;
}) {
  const openRouterKey = process.env['OPENROUTER_API_KEY'];
  const openRouterModel = process.env['OPENROUTER_API_MODEL'] || 'google/gemini-3.5-flash';

  if (openRouterKey) {
    console.log(`[LLM] routing to OpenRouter using model ${openRouterModel}`);
    
    let finalPrompt = options.prompt;
    const body: any = {
      model: openRouterModel,
    };

    if (options.responseSchema) {
      const standardSchema = convertGeminiSchemaToStandard(options.responseSchema);
      finalPrompt += `\n\nCRITICAL: You MUST respond with a JSON object that matches this JSON Schema exactly:
${JSON.stringify(standardSchema, null, 2)}`;
      
      body.response_format = {
        type: 'json_schema',
        json_schema: {
          name: 'response_schema',
          strict: false,
          schema: standardSchema
        }
      };
    }

    const content: any[] = [{ type: 'text', text: finalPrompt }];
    
    if (options.imagesBase64) {
      for (const img of options.imagesBase64) {
        content.push({
          type: 'image_url',
          image_url: { url: img }
        });
      }
    }

    body.messages = [{ role: 'user', content }];

    const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${openRouterKey}`,
        'HTTP-Referer': 'https://github.com/google/gemini-angular-sample',
        'X-Title': 'Plushie Pattern Generator'
      },
      body: JSON.stringify(body)
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`OpenRouter call failed (${res.status}): ${errText}`);
    }

    const result = await res.json();
    let text = result.choices?.[0]?.message?.content || '';
    
    text = text.trim();
    if (text.startsWith('```')) {
      text = text.replace(/^```[a-zA-Z]*\n?/, '').replace(/```$/, '').trim();
    }
    return text;
  } else {
    console.log('[LLM] routing to direct Google GenAI API');
    const parts: any[] = [];
    if (options.imagesBase64) {
      for (const imgWithMeta of options.imagesBase64) {
        if (imgWithMeta && imgWithMeta.startsWith('data:')) {
          const commaIndex = imgWithMeta.indexOf(',');
          const data = commaIndex !== -1 ? imgWithMeta.slice(commaIndex + 1) : imgWithMeta;
          const mimeStr = imgWithMeta.slice(5, commaIndex !== -1 ? imgWithMeta.indexOf(';base64') : 15);
          parts.push({
            inlineData: {
              mimeType: mimeStr || "image/png",
              data: data
            }
          });
        }
      }
    }
    parts.push({ text: options.prompt });

    const response = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: { parts },
      config: {
        responseMimeType: options.responseSchema ? "application/json" : undefined,
        responseSchema: options.responseSchema
      }
    });

    return response.text || '';
  }
}

const browserDistFolder = join(import.meta.dirname, '../browser');

const app = express();
const angularApp = new AngularNodeAppEngine();

app.use(express.json({ limit: '10mb' }));

app.post('/api/generate-images', async (req, res) => {
  try {
    const { prompt } = req.body;
    if (!prompt) {
      return res.status(400).json({ error: 'Prompt is required' });
    }

    const enhancedPrompt = `A cute clean vector illustration of ${prompt}, cute plush doll style, direct multi-angle reference view, solid soft background, flat graphics children design, simple details.`;

    try {
      const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash-image',
        contents: {
          parts: [{ text: enhancedPrompt }]
        },
        config: {
          imageConfig: {
            aspectRatio: "1:1"
          }
        }
      });

      let imageBase64 = null;
      if (response && response.candidates && response.candidates[0] && response.candidates[0].content && response.candidates[0].content.parts) {
        for (const part of response.candidates[0].content.parts) {
          if (part.inlineData) {
            imageBase64 = `data:image/png;base64,${part.inlineData.data}`;
            break;
          }
        }
      }

      if (imageBase64) {
        return res.json({ success: true, url: imageBase64 });
      } else {
        throw new Error('No image returned in response parts.');
      }
    } catch (apiError) {
      console.warn('Gemini image generation call failed. Generating custom vector SVG illustration.', apiError);
      
      try {
        const svgPrompt = `Generate a beautiful, extremely cute, flat vector SVG illustration of a character plushie doll matching this description: "${prompt}".
Requirements:
- Make it look like a stitched plush toy (use pastel colors, round outlines, and dotted/dashed stroke lines for seams).
- Ensure the SVG has viewBox="0 0 400 400" and occupies the full space.
- Respond with ONLY the raw <svg>...</svg> XML block.
- Do not output any markdown formatting (like \`\`\`xml) or commentary. Just the raw <svg> element.`;

        const svgResponse = await callLLM({ prompt: svgPrompt });
        
        let cleanedSvg = svgResponse.trim();
        if (cleanedSvg.includes('```')) {
          const match = cleanedSvg.match(/```(?:xml|svg|html)?\s*([\s\S]*?)```/);
          if (match && match[1]) {
            cleanedSvg = match[1].trim();
          }
        }
        
        const svgStart = cleanedSvg.indexOf('<svg');
        const svgEnd = cleanedSvg.lastIndexOf('</svg>');
        if (svgStart !== -1 && svgEnd !== -1) {
          cleanedSvg = cleanedSvg.substring(svgStart, svgEnd + 6);
        }

        if (cleanedSvg.startsWith('<svg')) {
          const base64Svg = Buffer.from(cleanedSvg).toString('base64');
          const dataUrl = `data:image/svg+xml;base64,${base64Svg}`;
          return res.json({
            success: true,
            url: dataUrl,
            isFallback: false
          });
        }
        
        throw new Error('Invalid SVG returned');
      } catch (fallbackError) {
        console.error('SVG fallback generation failed:', fallbackError);
        // Clean default cute Teddy SVG if everything else fails
        const defaultTeddySvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%">
          <rect width="400" height="400" fill="#FAF9F6" rx="20"/>
          <rect x="10" y="10" width="380" height="380" fill="none" stroke="#78716C" stroke-width="2" stroke-dasharray="8,6" rx="15"/>
          <circle cx="200" cy="200" r="100" fill="#D6D3D1" stroke="#78716C" stroke-width="3" stroke-dasharray="5,4"/>
          <circle cx="120" cy="110" r="30" fill="#D6D3D1" stroke="#78716C" stroke-width="3" stroke-dasharray="5,4"/>
          <circle cx="120" cy="110" r="15" fill="#F5F5F4"/>
          <circle cx="280" cy="110" r="30" fill="#D6D3D1" stroke="#78716C" stroke-width="3" stroke-dasharray="5,4"/>
          <circle cx="280" cy="110" r="15" fill="#F5F5F4"/>
          <ellipse cx="200" cy="230" rx="35" ry="25" fill="#F5F5F4" stroke="#78716C" stroke-width="2" stroke-dasharray="4,3"/>
          <polygon points="200,215 190,225 210,225" fill="#44403C"/>
          <path d="M 200 225 Q 200 240 190 240 M 200 225 Q 200 240 210 240" fill="none" stroke="#44403C" stroke-width="2"/>
          <circle cx="165" cy="180" r="8" fill="#44403C"/>
          <circle cx="235" cy="180" r="8" fill="#44403C"/>
          <circle cx="140" cy="205" r="12" fill="#FECDD3" opacity="0.7"/>
          <circle cx="260" cy="205" r="12" fill="#FECDD3" opacity="0.7"/>
          <text x="200" y="340" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="bold" fill="#78716C">Plushie Concept Draft</text>
        </svg>`;
        const base64Default = Buffer.from(defaultTeddySvg).toString('base64');
        return res.json({
          success: true,
          url: `data:image/svg+xml;base64,${base64Default}`,
          isFallback: true
        });
      }
    }
  } catch (error) {
    console.error('Error in /api/generate-images:', error);
    res.status(500).json({ error: 'Failed to generate character ideas' });
    return;
  }
});

app.post('/api/analyze-complexity', async (req, res) => {
  try {
    const { imagesBase64 } = req.body;
    const parts: { inlineData?: { mimeType: string; data: string }; text?: string }[] = [];
    
    if (imagesBase64 && Array.isArray(imagesBase64)) {
      for (const imgWithMeta of imagesBase64) {
        if (imgWithMeta && imgWithMeta.startsWith('data:')) {
          const commaIndex = imgWithMeta.indexOf(',');
          const data = commaIndex !== -1 ? imgWithMeta.slice(commaIndex + 1) : imgWithMeta;
          const mimeStr = imgWithMeta.slice(5, commaIndex !== -1 ? imgWithMeta.indexOf(';base64') : 15);
          parts.push({
            inlineData: {
              mimeType: mimeStr || "image/png",
              data: data
            }
          });
        }
      }
    }

    const textPrompt = `Analyze the uploaded plushie character image reference. Assess step-by-step sewing complexity and design cutting paper templates for each sub-piece. You MUST return a valid JSON structure matching the required schema. Include difficulty (Novice, Scout, Artisan), reasoning, sewing machine settings suggestions, required fabrics, and 5-8 layout cutting pieces representing geometric templates (circle, rect, oval, triangle, shield) with height/width sizes so users can arrange them visually, plus interactive customization options. Detailed prompt logic applies.`;

    parts.push({ text: textPrompt });

    const responseText = await callLLM({
      prompt: textPrompt,
      imagesBase64: imagesBase64,
      responseSchema: {
        type: Type.OBJECT,
        required: ["difficulty", "difficultyReasoning", "sewingMachineVsHand", "estimatedTime", "requiredFabrics", "cuttingLayoutSize", "cuttingPieces", "customizationOptions"],
        properties: {
          difficulty: { type: Type.STRING },
          difficultyReasoning: { type: Type.STRING },
          sewingMachineVsHand: { type: Type.STRING },
          estimatedTime: { type: Type.STRING },
          requiredFabrics: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              required: ["fabricName", "amountRequired", "color", "textureRecommendation"],
              properties: {
                fabricName: { type: Type.STRING },
                amountRequired: { type: Type.STRING },
                color: { type: Type.STRING },
                textureRecommendation: { type: Type.STRING }
              }
            }
          },
          cuttingLayoutSize: {
            type: Type.OBJECT,
            required: ["width", "height"],
            properties: {
              width: { type: Type.INTEGER },
              height: { type: Type.INTEGER }
            }
          },
          cuttingPieces: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              required: ["id", "name", "shapeType", "color", "count", "label", "width", "height"],
              properties: {
                id: { type: Type.STRING },
                name: { type: Type.STRING },
                shapeType: { type: Type.STRING, description: "Must be: circle, rect, oval, triangle, or shield" },
                color: { type: Type.STRING },
                count: { type: Type.INTEGER },
                label: { type: Type.STRING },
                width: { type: Type.INTEGER },
                height: { type: Type.INTEGER }
              }
            }
          },
          customizationOptions: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              required: ["optionId", "optionTitle", "selectionType", "choices", "defaultValue", "description"],
              properties: {
                optionId: { type: Type.STRING },
                optionTitle: { type: Type.STRING },
                selectionType: { type: Type.STRING },
                choices: { type: Type.ARRAY, items: { type: Type.STRING } },
                defaultValue: { type: Type.STRING },
                description: { type: Type.STRING }
              }
            }
          }
        }
      }
    });

    const parsedResult = JSON.parse(responseText || '{}');
    res.json(parsedResult);
    return;
  } catch (error) {
    console.error('Error analyzing complexity:', error);
    res.status(500).json({ error: 'Failed to analyze design complexity. Please ensure images are valid.' });
    return;
  }
});

app.post('/api/generate-plushie-preview', async (req, res) => {
  try {
    const { customizations, refinementPrompt } = req.body;
    
    const cutsDescription = Object.entries(customizations || {})
      .map(([k, v]) => `- ${k}: Selected ${v}`)
      .join('\n');

    const previewPrompt = `A high quality gorgeous workshop photo of a finished, professional stitched handmade character plushie sitting on a wood cutting board on a tailor's table.
Chosen Customizations:
${cutsDescription}
${refinementPrompt ? `User Adjustment requests: ${refinementPrompt}` : ''}
The toy features perfect needlework seams, soft plush fabric texture, warm accent craft lighting. Beautiful commercial craft product photo.`;

    try {
      const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash-image',
        contents: {
          parts: [{ text: previewPrompt }]
        },
        config: {
          imageConfig: {
            aspectRatio: "4:3"
          }
        }
      });

      let imageBase64 = null;
      if (response && response.candidates && response.candidates[0] && response.candidates[0].content && response.candidates[0].content.parts) {
        for (const part of response.candidates[0].content.parts) {
          if (part.inlineData) {
            imageBase64 = `data:image/png;base64,${part.inlineData.data}`;
            break;
          }
        }
      }

      if (imageBase64) {
        return res.json({ url: imageBase64, desc: "Successfully custom-rendered finished preview model." });
      } else {
        throw new Error('No inline image base64 returned.');
      }
    } catch (apiError) {
      console.warn('Real plushie preview rendering call failed. Generating custom preview SVG illustration.', apiError);
      
      try {
        const customPrompt = `Generate a beautiful, gorgeous flat vector SVG illustration of a custom plushie character based on the following configurations:
Customizations:
${cutsDescription}
${refinementPrompt ? `Refinement Prompt: ${refinementPrompt}` : ''}
Requirements:
- Make it look like a finished, professional stitched handmade plush toy (use pastel colors, round outlines, and dotted/dashed stroke lines for seams).
- Ensure the SVG has viewBox="0 0 600 450" and occupies the full space.
- Respond with ONLY the raw <svg>...</svg> XML block.
- Do not output any markdown formatting (like \`\`\`xml) or commentary. Just the raw <svg> element.`;

        const svgResponse = await callLLM({ prompt: customPrompt });
        
        let cleanedSvg = svgResponse.trim();
        if (cleanedSvg.includes('```')) {
          const match = cleanedSvg.match(/```(?:xml|svg|html)?\s*([\s\S]*?)```/);
          if (match && match[1]) {
            cleanedSvg = match[1].trim();
          }
        }
        
        const svgStart = cleanedSvg.indexOf('<svg');
        const svgEnd = cleanedSvg.lastIndexOf('</svg>');
        if (svgStart !== -1 && svgEnd !== -1) {
          cleanedSvg = cleanedSvg.substring(svgStart, svgEnd + 6);
        }

        if (cleanedSvg.startsWith('<svg')) {
          const base64Svg = Buffer.from(cleanedSvg).toString('base64');
          const dataUrl = `data:image/svg+xml;base64,${base64Svg}`;
          return res.json({
            url: dataUrl,
            desc: "Custom SVG conceptual model mapped for chosen details."
          });
        }
        
        throw new Error('Invalid SVG returned');
      } catch (fallbackError) {
        console.error('Custom preview SVG generation failed:', fallbackError);
        // Default clean custom preview SVG if everything else fails
        const defaultPreviewSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 450" width="100%" height="100%">
          <rect width="600" height="450" fill="#EFECE6" rx="20"/>
          <rect x="20" y="20" width="560" height="410" fill="none" stroke="#78716C" stroke-width="2" stroke-dasharray="10,8" rx="15"/>
          <ellipse cx="300" cy="225" rx="140" ry="110" fill="#D6D3D1" stroke="#78716C" stroke-width="3" stroke-dasharray="6,4"/>
          <circle cx="300" cy="180" r="70" fill="#E7E5E4" stroke="#78716C" stroke-width="2" stroke-dasharray="5,4"/>
          <circle cx="280" cy="170" r="6" fill="#44403C"/>
          <circle cx="320" cy="170" r="6" fill="#44403C"/>
          <path d="M 290 190 Q 300 200 310 190" fill="none" stroke="#44403C" stroke-width="2"/>
          <text x="300" y="380" text-anchor="middle" font-family="sans-serif" font-size="14" font-weight="bold" fill="#78716C">Finished Plushie Preview Model</text>
        </svg>`;
        const base64Default = Buffer.from(defaultPreviewSvg).toString('base64');
        return res.json({
          url: `data:image/svg+xml;base64,${base64Default}`,
          desc: "Default plushie preview model placeholder."
        });
      }
    }
  } catch (error) {
    console.error('Error in /api/generate-plushie-preview:', error);
    res.status(500).json({ error: 'Failed to render outcome companion design.' });
    return;
  }
});

app.post('/api/generate-build-guide', async (req, res) => {
  try {
    const { complexityResult, customizations, refinementPrompt } = req.body;

    const cutsDescription = Object.entries(customizations || {})
      .map(([k, v]) => `- ${k}: ${v}`)
      .join('\n');

    const guidePrompt = `Design a comprehensive, highly accessible step-by-step master sewing pattern and build guide for a custom plushie toy based on the following configurations:
Estimated Difficulty: ${complexityResult?.difficulty || 'Novice'}
Fabric Materials: ${JSON.stringify(complexityResult?.requiredFabrics || [])}
Customization Choices Made:
${cutsDescription}
${refinementPrompt ? `Extra User Refinement requests: ${refinementPrompt}` : ''}

You MUST output structured step-by-step sewing actions. Structure the response strictly in JSON format matching the schema properties so the beginner can follow easily. Include tension, stitch types, prep, stitch orders, closing steps, and expert tailor tips.`;

    const responseText = await callLLM({
      prompt: guidePrompt,
      responseSchema: {
        type: Type.OBJECT,
        required: ["sewingMachineSettings", "materialsList", "preparationSteps", "stitchingSteps", "finishingSteps", "tailoringProTips"],
        properties: {
          sewingMachineSettings: {
            type: Type.OBJECT,
            required: ["tension", "stitchType", "needleType"],
            properties: {
              tension: { type: Type.STRING },
              stitchType: { type: Type.STRING },
              needleType: { type: Type.STRING }
            }
          },
          materialsList: {
            type: Type.ARRAY,
            items: { type: Type.STRING }
          },
          preparationSteps: {
            type: Type.ARRAY,
            items: { type: Type.STRING }
          },
          stitchingSteps: {
            type: Type.ARRAY,
            items: { type: Type.STRING }
          },
          finishingSteps: {
            type: Type.ARRAY,
            items: { type: Type.STRING }
          },
          tailoringProTips: {
            type: Type.ARRAY,
            items: { type: Type.STRING }
          }
        }
      }
    });

    const parsedGuide = JSON.parse(responseText || '{}');
    res.json(parsedGuide);
    return;
  } catch (error) {
    console.error('Error generating build guide:', error);
    res.status(500).json({ error: 'Failed to compile final builder steps' });
    return;
  }
});

/**
 * Example Express Rest API endpoints can be defined here.
 * Uncomment and define endpoints as necessary.
 *
 * Example:
 * ```ts
 * app.get('/api/{*splat}', (req, res) => {
 *   // Handle API request
 * });
 * ```
 */

/**
 * Serve static files from /browser
 */
app.use(
  express.static(browserDistFolder, {
    maxAge: '1y',
    index: false,
    redirect: false,
  }),
);

/**
 * Handle all other requests by rendering the Angular application.
 */
app.use((req, res, next) => {
  angularApp
    .handle(req)
    .then((response) =>
      response ? writeResponseToNodeResponse(response, res) : next(),
    )
    .catch(next);
});

/**
 * Start the server if this module is the main entry point, or it is ran via PM2.
 * The server listens on the port defined by the `PORT` environment variable, or defaults to 4000.
 */
if (isMainModule(import.meta.url) || process.env['pm_id']) {
  const port = process.env['PORT'] || 4000;
  app.listen(port, (error) => {
    if (error) {
      throw error;
    }

    console.log(`Node Express server listening on http://localhost:${port}`);
  });
}

/**
 * Request handler used by the Angular CLI (for dev-server and during build) or Firebase Cloud Functions.
 */
export const reqHandler = createNodeRequestHandler(app);
