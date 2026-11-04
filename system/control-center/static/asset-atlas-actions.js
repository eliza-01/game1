/* Cross-domain Atlas Registry client. No model/house ownership or Studio side effects. */
window.game1AtlasWorkflow = (() => {
  const post = (url, body = {}) => request(url, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  function variantId(value) {
    const id = Number(value);
    if (!Number.isSafeInteger(id) || id < 1) throw Error('Choose a registered atlas variant');
    return id;
  }
  return Object.freeze({
    register: (sourcePath) => post('/api/texture-atlases/variants', {sourcePath}),
    publish: (id) => post(`/api/texture-atlases/variants/${variantId(id)}/publish`),
    republish: (id, sourcePath) => {
      if (!String(sourcePath || '').trim()) throw Error('Choose a changed atlas image first');
      return post(`/api/texture-atlases/variants/${variantId(id)}/republish`, {sourcePath});
    },
    chooseImage: (pickerEndpoint) => post(pickerEndpoint),
  });
})();
