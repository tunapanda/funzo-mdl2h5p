/**
 * RadioGroup widget
 *
 * @param {H5P.jQuery} $
 */
H5PEditor.RadioGroup = H5PEditor.widgets.radioGroup = (function ($) {

  var groupCounter = 0;
  /**
   * Creates an radio button group.
   *
   * @class H5PEditor.ImageRadioButtonGroup
   * @param {Object} parent
   * @param {Object} field
   * @param {Object} params
   * @param {function} setValue
   */
  function RadioGroup(parent, field, params, setValue) {
    this.parent = parent;
    this.field = field;
    this.params = params;
    this.setValue = setValue;

    this.alignment = this.field.alignment || 'vertical';

    groupCounter++;
  }

  /**
   * Append the field to the wrapper.
   * @public
   * @param {H5P.jQuery} $wrapper
   */
  RadioGroup.prototype.appendTo = function ($wrapper) {
    var self = this;

    self.$container = $('<div>', {
      'class': 'field text h5p-editor-radio-group'
    });

    // Add header:
    $('<div>', {
      'class': 'h5peditor-label',
      html: self.field.label
    }).appendTo(self.$container);

    var $buttonGroup = $('<div>', {
      'class': 'h5p-editor-radio-group-container ' + this.alignment,
      role: 'radiogroup'
    }).appendTo(self.$container);

    for (var i=0, numOptions = self.field.options.length; i < numOptions; i++) {
      var option = self.field.options[i];
      var inputId = 'h5p-editor-radio-group-button-' + groupCounter + '-' + i;

      var $button = $('<div>', {
        'class': 'h5p-editor-radio-group-button ' + option.value
      }).appendTo($buttonGroup);

      $('<input>', {
        type: 'radio',
        name: self.field.name + groupCounter,
        value: option.value,
        role: 'radio',
        id: inputId,
        checked: (self.params === option.value) || (self.params === undefined && this.field.default === option.value),
        change: function () {
          self.params = $('input:checked', $buttonGroup).val();
          self.setValue(self.field, self.params);
        }
      }).appendTo($button);

      $('<label>', {
        'for': inputId
      }).append($('<span>', {
        html: option.label
      })).appendTo($button);

      if (option.description) {
        $('<div>', {
          'class': 'h5p-option-description',
          html: option.description
        }).appendTo($button);
      }
    }

    // Add description:
    $('<div>', {
      'class': 'h5peditor-field-description',
      html: self.field.description
    }).appendTo(self.$container);

    self.$container.appendTo($wrapper);
  };


  /**
   * Validate the current values.
   */
  RadioGroup.prototype.validate = function () {
    return true;
  };

  RadioGroup.prototype.remove = function () {};

  return RadioGroup;
})(H5P.jQuery);
