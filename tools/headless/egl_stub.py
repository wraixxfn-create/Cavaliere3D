import subprocess, os, re, json

OUT="/home/user/wsx-libs"
EXTRA=f"{OUT}/egl_extra.json"

EGL_BASE = """eglBindAPI eglBindTexImage eglChooseConfig eglClientWaitSync eglCopyBuffers eglCreateContext
eglCreateDevice eglCreateImage eglCreatePbufferFromClientBuffer eglCreatePbufferSurface eglCreatePixmapSurface
eglCreatePlatformPixmapSurface eglCreatePlatformWindowSurface eglCreateSync eglCreateWindowSurface
eglDestroyContext eglDestroyImage eglDestroySync eglDestroySurface eglGetConfigAttrib eglGetConfigs
eglGetCurrentContext eglGetCurrentDisplay eglGetCurrentSurface eglGetDisplay eglGetError
eglGetPlatformDisplay eglGetProcAddress eglGetSyncAttrib eglInitialize eglMakeCurrent eglQueryAPI
eglQueryContext eglQueryDeviceAttrib eglQueryDeviceString eglQueryDisplayAttrib eglQueryString
eglQuerySurface eglReleaseTexImage eglReleaseThread eglSurfaceAttrib eglSwapBuffers eglSwapInterval
eglTerminate eglWaitClient eglWaitGL eglWaitNative eglCreatePlatformWindowSurfaceEXT
eglCreatePlatformPixmapSurfaceEXT eglGetPlatformDisplayEXT eglQueryDeviceAttribEXT
eglQueryDisplayAttribEXT eglQueryDevicesEXT eglGetNativeClientBufferANDROID
eglDupNativeFenceFDANDROID eglCreateSyncKHR eglDestroySyncKHR eglClientWaitSyncKHR
eglGetSyncAttribKHR eglCreateImageKHR eglDestroyImageKHR eglSwapBuffersWithDamageKHR eglGetDisplayDriverName""".split()

GLES = """glActiveTexture glBindBuffer glBindFramebuffer glBindRenderbuffer glBindTexture glBlendEquation
glBlendFunc glBlendFuncSeparate glBufferData glBufferSubData glCheckFramebufferStatus glClear
glClearColor glClearDepthf glClearStencil glColorMask glCompileShader glCompressedTexImage2D
glCompressedTexSubImage2D glCopyTexImage2D glCopyTexSubImage2D glCreateProgram glCreateShader
glCullFace glDeleteBuffers glDeleteFramebuffers glDeleteProgram glDeleteRenderbuffers glDeleteShader
glDeleteTextures glDepthFunc glDepthMask glDepthRangef glDetachShader glDisable glDisableVertexAttribArray
glDrawArrays glDrawElements glEnable glEnableVertexAttribArray glFinish glFlush glFramebufferRenderbuffer
glFramebufferTexture2D glFrontFace glGenBuffers glGenFramebuffers glGenRenderbuffers glGenTextures
glGenerateMipmap glGetActiveAttrib glGetActiveUniform glGetAttachedShaders glGetAttribLocation
glGetBooleanv glGetBufferParameteriv glGetError glGetFloatv glGetFramebufferAttachmentParameteriv
glGetIntegerv glGetProgramInfoLog glGetProgramiv glGetRenderbufferParameteriv glGetShaderInfoLog
glGetShaderPrecisionFormat glGetShaderSource glGetShaderiv glGetString glGetStringi glGetTexParameterfv
glGetTexParameteriv glGetUniformLocation glGetUniformfv glGetUniformiv glGetVertexAttribPointerv
glGetVertexAttribfv glGetVertexAttribiv glHint glIsBuffer glIsEnabled glIsFramebuffer glIsProgram
glIsRenderbuffer glIsShader glIsTexture glLineWidth glLinkProgram glPixelStorei glPolygonOffset
glReadPixels glReleaseShaderCompiler glRenderbufferStorage glRenderbufferStorageMultisample
glSampleCoverage glScissor glShaderBinary glShaderSource glStencilFunc glStencilFuncSeparate
glStencilMask glStencilMaskSeparate glStencilOp glStencilOpSeparate glTexImage2D glTexParameterf
glTexParameterfv glTexParameteri glTexParameteriv glTexSubImage2D glUniform1f glUniform1fv glUniform1i
glUniform1iv glUniform2f glUniform2fv glUniform2i glUniform2iv glUniform3f glUniform3fv glUniform3i
glUniform3iv glUniform4f glUniform4fv glUniform4i glUniform4iv glUniformMatrix2fv glUniformMatrix3fv
glUniformMatrix4fv glUseProgram glValidateProgram glVertexAttrib1f glVertexAttrib1fv glVertexAttrib2f
glVertexAttrib2fv glVertexAttrib3f glVertexAttrib3fv glVertexAttrib4f glVertexAttrib4fv
glVertexAttribPointer glViewport glReadBuffer glDrawBuffer glMapBuffer glUnmapBuffer glBlitFramebuffer
glGetBufferSubData glTexStorage2D glTexStorage3D""".split()

def build(symbols_egl, symbols_gles):
    for lib, names in (("libEGL.so.1", sorted(set(EGL_BASE + symbols_egl))),
                       ("libGLESv2.so.2", sorted(set(GLES + symbols_gles))),
                       ("libGLESv1_CM.so.1", sorted(set(GLES + symbols_gles)))):
        src = "\n".join(f"void *{n}(void){{return 0;}}" for n in names)
        open(f"{OUT}/egl_tmp.c","w").write(src+"\n")
        r = subprocess.run(["gcc","-shared","-fPIC",f"-Wl,-soname,{lib}","-o",f"{OUT}/{lib}",f"{OUT}/egl_tmp.c"],
                           capture_output=True, text=True)
        if r.returncode: print("FAIL", lib, r.stderr[:600]); return False
    return True

extra = json.load(open(EXTRA)) if os.path.exists(EXTRA) else {"egl": [], "gles": []}
if not build(extra["egl"], extra["gles"]): raise SystemExit(1)
env = dict(os.environ, LD_LIBRARY_PATH=OUT)
for i in range(80):
    r = subprocess.run(["/home/user/Cavaliere3D/.venv/bin/python","/home/user/Cavaliere3D/tools/check_cycles.py"],
                       capture_output=True, text=True, env=env, cwd="/home/user/Cavaliere3D")
    out = r.stdout + r.stderr
    if "RENDER OK" in out or "RENDER FAILED" in out or "OPENED OK" in out and "not found" not in out:
        print(out[-3000:]); break
    m = re.search(r"(\S+) not found:.*undefined symbol: (\S+)", out)
    if not m:
        print("NO PATTERN:\n", out[-2500:]); break
    _, sym = m.groups()
    key = "egl" if sym.startswith("egl") else "gles"
    if sym in extra[key]:
        print("LOOP", sym); print(out[-1500:]); break
    extra[key].append(sym)
    json.dump(extra, open(EXTRA,"w"))
    if not build(extra["egl"], extra["gles"]): break
